"""Build data/yale_courses.json: every Yale school's courses for one term.

Source: Yale Course Search (courses.yale.edu), the university's official
catalogue. SOM keeps its own richer listing (data/yale_som_classes.json: rooms,
bidding, faculty bios), so Yale Course Search's SOM rows are skipped and the SOM
file is merged in instead.

Every row uses the same keys as yale_som_classes.json, plus School fields, so
the backend, the agent and the React cards read one shape.

Run from backend/:
    .venv/bin/python fetch_yale_courses.py --term 202603
"""

from __future__ import annotations

import argparse
import html
import json
import re
import time
from urllib.parse import quote
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent

BASE = "https://courses.yale.edu"
API = f"{BASE}/api/?page=fose&route="
# The site answers bare scripts with an empty 202; a browser user agent gets data.
UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
)
SOM_CODE = "MG"
DAY_CODES = ["Mo", "Tu", "We", "Th", "Fr", "Sa", "Su"]


def strip_html(raw: str) -> str:
    """HTML fragment → plain text, paragraphs kept on their own lines."""
    text = re.sub(r"</p>|<br\s*/?>|</div>", "\n", raw or "", flags=re.I)
    text = html.unescape(re.sub(r"<[^>]+>", "", text))
    lines = [" ".join(line.split()) for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def select_options(page: str, select_id: str) -> dict[str, str]:
    """Value → label for one <select> on the Yale Course Search home page."""
    block = re.search(rf'<select[^>]*id="{select_id}"[^>]*>(.*?)</select>', page, re.S)
    if not block:
        return {}
    return {
        html.unescape(value): html.unescape(label).strip()
        for value, label in re.findall(r'<option value="([^"]*)"[^>]*>([^<]*)', block.group(1))
        if value
    }


def clock(hhmm: str) -> str:
    """'1005' → '10:05 AM'."""
    if not hhmm or not hhmm.isdigit():
        return ""
    hour, minute = divmod(int(hhmm), 100)
    suffix = "AM" if hour < 12 else "PM"
    return f"{(hour - 1) % 12 + 1}:{minute:02d} {suffix}"


def to_row(hit: dict, detail: dict, schools: dict, subjects: dict, schedules: dict) -> dict:
    """One Yale Course Search section → the yale_som_classes.json row shape."""
    code = hit["code"]
    subject = code.split(" ")[0]

    try:
        meetings = json.loads(hit.get("meetingTimes") or "[]")
    except json.JSONDecodeError:
        meetings = []
    days = sorted({int(m["meet_day"]) for m in meetings if str(m.get("meet_day", "")).isdigit()})
    first = meetings[0] if meetings else {}

    meets = [m for m in strip_html(detail.get("meeting_html", "")).splitlines() if m]
    if len(meets) > 1:
        meets = [m for m in meets if m != "HTBA"]

    names = [strip_html(n) for n in re.findall(r'class="instructor-name">(.*?)</div>', detail.get("instructordetail_html", ""), re.S)]
    emails = re.findall(r"mailto:([^\"']+)", detail.get("instructordetail_html", ""))
    syllabus = next(
        (url for url in re.findall(r'href="(https?://[^"]+)"', detail.get("resources", "")) if "syllabus" in url.lower()),
        "",
    )
    same_as = re.sub(r"^Same As:\s*", "", strip_html(detail.get("xlist", "")))

    return {
        "Course ID": hit["crn"],
        "Course Number": code,
        "Course Title": html.unescape(hit.get("title", "")),
        "Course Category": subjects.get(subject, subject),
        "Course Type": schedules.get(hit.get("schd", ""), ""),
        "Course Description": strip_html(detail.get("description", "")),
        "Course Session": "",
        "Course Session Start date": hit.get("start_date", ""),
        "Course Session End Date": hit.get("end_date", ""),
        "Faculty 1": "; ".join(n for n in names if n) or hit.get("instr", ""),
        "Faculty 1 Email": "; ".join(dict.fromkeys(emails)),
        "faculty_bio": "",
        "Daytimes": "; ".join(meets) or hit.get("meets", ""),
        "Timings Day": " ".join(DAY_CODES[d] for d in days if d < len(DAY_CODES)),
        "Timings StartTime": clock(str(first.get("start_time", ""))),
        "Timings EndTime": clock(str(first.get("end_time", ""))),
        "Room": "",
        "Section": hit.get("no", ""),
        "Units": strip_html(detail.get("credit_html", "")),
        "Bid Or Permission": "",
        "Syllabus": syllabus,
        "Old Syllabus": "",
        "TermCode": hit.get("srcdb", ""),
        "Visible": "1",
        "School": schools.get(hit.get("col", ""), hit.get("col", "")),
        "School Code": hit.get("col", ""),
        "Subject": subject,
        "Same As": same_as,
        # The same deep link Yale Course Search's own "share" button builds.
        "Source URL": f"{BASE}/?details&srcdb={hit.get('srcdb', '')}&code={quote(code)}",
    }


def group_sections(rows: list[dict]) -> list[dict]:
    """One row per course: discussion and lab sections fold into the first section.

    Instructors, emails and meeting days are unioned so a search still finds the
    course by any section's teacher or day; "Sections" keeps the count.
    """
    groups: dict[tuple[str, str, str], list[dict]] = {}
    for row in sorted(rows, key=lambda r: (r["School"], r["Course Number"], r["Section"])):
        groups.setdefault((row["School Code"], row["Course Number"], row["Course Title"]), []).append(row)

    def union(values: list[str], sep: str) -> str:
        seen = dict.fromkeys(part.strip() for value in values for part in value.split(sep) if part.strip())
        return sep.join(seen)

    out = []
    for sections in groups.values():
        lead = dict(sections[0])
        lead["Sections"] = len(sections)
        lead["Faculty 1"] = union([s["Faculty 1"] for s in sections], "; ")
        lead["Faculty 1 Email"] = union([s["Faculty 1 Email"] for s in sections], "; ")
        days = {d for s in sections for d in s["Timings Day"].split()}
        lead["Timings Day"] = " ".join(d for d in DAY_CODES if d in days)
        out.append(lead)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--term", default="202603", help="Yale term code, e.g. 202603 = Fall 2026")
    parser.add_argument("--som-file", type=Path, default=ROOT / "data" / "yale_som_classes.json")
    parser.add_argument("--out", type=Path, default=ROOT / "data" / "yale_courses.json")
    parser.add_argument("--workers", type=int, default=6, help="Parallel detail requests")
    args = parser.parse_args()

    client = httpx.Client(headers={"User-Agent": UA}, timeout=60.0)

    home = client.get(f"{BASE}/").text
    schools = select_options(home, "crit-col")
    subjects = {k: re.sub(r"\s*\([^)]*\)$", "", v) for k, v in select_options(home, "crit-subject").items()}
    schedules = select_options(home, "crit-schd")
    terms = select_options(home, "crit-srcdb")
    if not schools:
        raise SystemExit("Could not read the school list from courses.yale.edu.")
    print(f"Term {args.term} ({terms.get(args.term, 'unknown')}), {len(schools)} schools")

    hits: list[dict] = []
    for col, name in schools.items():
        if col == SOM_CODE:
            continue
        found = client.post(
            f"{API}search",
            json={"other": {"srcdb": args.term}, "criteria": [{"field": "col", "value": col}]},
        ).json().get("results", [])
        found = [h for h in found if not h.get("isCancelled") and h.get("stat") != "C"]
        print(f"  {name}: {len(found)} sections")
        hits.extend(found)

    def details(hit: dict) -> tuple[dict, dict]:
        body = {
            "group": f"code:{hit['code']}",
            "key": f"crn:{hit['crn']}",
            "srcdb": args.term,
            "matched": f"crn:{hit['crn']}",
        }
        for attempt in range(4):
            try:
                response = client.post(f"{API}details", json=body)
                response.raise_for_status()
                return hit, response.json()
            except (httpx.HTTPError, json.JSONDecodeError):
                time.sleep(2 * (attempt + 1))
        return hit, {}

    rows: list[dict] = []
    missing = 0
    with ThreadPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(details, h) for h in hits]
        for done, future in enumerate(as_completed(futures), start=1):
            hit, detail = future.result()
            missing += not detail
            rows.append(to_row(hit, detail, schools, subjects, schedules))
            if done % 500 == 0:
                print(f"  details {done}/{len(hits)}")

    som = json.loads(args.som_file.read_text(encoding="utf-8"))
    for row in som:
        row.update(
            {
                "School": schools.get(SOM_CODE, "School of Management"),
                "School Code": SOM_CODE,
                "Subject": row.get("Course Number", "").split(" ")[0],
                "Same As": "",
                "Source URL": "",
            }
        )

    courses = group_sections(rows)
    merged = som + courses
    args.out.write_text(json.dumps(merged, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(
        f"Wrote {len(merged)} rows ({len(som)} SOM + {len(courses)} courses from "
        f"{len(rows)} sections in other schools) to {args.out}"
    )
    if missing:
        print(f"WARNING: {missing} sections have no detail record (description, instructors).")


if __name__ == "__main__":
    main()
