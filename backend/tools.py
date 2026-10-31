"""The two agent tools: search_courses over the local JSON, web_search over the public web.

Both are plain functions with typed signatures and docstrings, so pydantic-ai can
expose them directly and the tool names the model calls are exactly
"search_courses" and "web_search". main.py reuses find_courses() for the catalog
API, so the website and the agent search the same way.
"""

from __future__ import annotations

import html
import json
import re
from functools import lru_cache
from pathlib import Path

import httpx

from models import Course, CourseSearchResult, WebResult, WebSearchResult

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
# Every Yale school (built by fetch_yale_courses.py); the SOM-only file is the fallback.
DATA_PATH = ROOT / "data" / "yale_courses.json"
SOM_DATA_PATH = ROOT / "data" / "yale_som_classes.json"

MAX_COURSE_RESULTS = 15
MAX_WEB_RESULTS = 5

# 'Timings Day' uses two-letter codes ("We") and 'Daytimes' uses single letters
# ("W 4:10 PM-7:10 PM"), so "Tuesday" has to be expanded to reach both. These are
# matched against the day fields only — never the description, where a bare "t"
# would hit almost every row.
DAY_ALIASES = {
    "monday": ["mo", "m"],
    "mon": ["mo", "m"],
    "tuesday": ["tu", "t"],
    "tue": ["tu", "t"],
    "tues": ["tu", "t"],
    "wednesday": ["we", "w"],
    "wed": ["we", "w"],
    "thursday": ["th"],
    "thu": ["th"],
    "thurs": ["th"],
    "friday": ["fr", "f"],
    "fri": ["fr", "f"],
    "saturday": ["sa"],
    "sat": ["sa"],
    "sunday": ["su"],
    "sun": ["su"],
}

STOPWORDS = {
    "a", "an", "and", "any", "are", "class", "classes", "course", "courses",
    "do", "does", "for", "have", "in", "is", "list", "me", "of", "on", "or",
    "show", "some", "taught", "teach", "teaches", "that", "the", "there",
    "what", "which", "who", "with",
}


def data_path() -> Path:
    return DATA_PATH if DATA_PATH.exists() else SOM_DATA_PATH


@lru_cache(maxsize=1)
def load_rows() -> list[dict]:
    """Raw rows, exactly as the React cards expect them."""
    path = data_path()
    if not path.exists():
        return []
    return json.loads(path.read_text(encoding="utf-8"))


@lru_cache(maxsize=1)
def load_courses() -> list[Course]:
    """Validated rows, index-aligned with load_rows()."""
    return [Course.model_validate(row) for row in load_rows()]


@lru_cache(maxsize=1)
def _haystacks() -> list[tuple[str, str, str]]:
    """(everything, title + numbers, day fields) per course, lower-cased once."""
    return [
        (c.haystack(), f"{c.number} {c.same_as} {c.title}".lower(), f"{c.day} {c.daytimes}".lower())
        for c in load_courses()
    ]


def _matches(hay: tuple[str, str, str], token: str) -> int:
    """0 if one query token misses this course, else a relevance weight.

    Day names are checked against the day fields only; every other token must
    start a word ("art" finds "Art History", not "Start-ups"). A hit in the
    title or course number counts more than one in the description.
    """
    everything, headline, days = hay
    codes = DAY_ALIASES.get(token)
    if codes:
        return 1 if any(re.search(rf"\b{code}", days) for code in codes) else 0
    pattern = re.compile(rf"(?<![a-z0-9]){re.escape(token)}")
    if pattern.search(headline):
        return 3
    return 1 if pattern.search(everything) else 0


def school_matches(course: Course, school: str) -> bool:
    """School filter: a code ("YC") or any part of the name ("medicine")."""
    wanted = (school or "").strip().lower()
    if not wanted or wanted == "all":
        return True
    return wanted == course.school_code.lower() or wanted in course.school.lower()


def find_courses(query: str = "", school: str = "", category: str = "", loose: bool = False) -> list[int]:
    """Indices of matching courses, best matches first.

    Every query word must match. With loose=True (the agent's tool), a query
    that matches nothing falls back to "any word" so it still gets leads.
    """
    courses = load_courses()
    hays = _haystacks()
    wanted_category = (category or "").strip().lower()
    pool = [
        i
        for i, c in enumerate(courses)
        if school_matches(c, school)
        and (not wanted_category or wanted_category == "all" or c.category.strip().lower() == wanted_category)
    ]

    cleaned = (query or "").lower().strip()
    tokens = [t for t in re.split(r"[^\w:]+", cleaned) if t and t not in STOPWORDS]
    if not tokens:
        return pool

    scored = []
    for i in pool:
        weights = [_matches(hays[i], tok) for tok in tokens]
        if all(weights):
            scored.append((-sum(weights), i))
    if not scored and loose:
        for i in pool:
            weight = sum(_matches(hays[i], tok) for tok in tokens)
            if weight:
                scored.append((-weight, i))
    scored.sort()
    return [i for _, i in scored]


def search_courses(query: str, school: str = "", limit: int = MAX_COURSE_RESULTS) -> dict:
    """Search the Yale course catalog for every school (Fall 2026).

    Matches against course title, course number (and cross-listed numbers),
    subject, faculty name, meeting day and time, room and the course
    description. Narrow by school with the school argument, not the query.
    Use this for any question the course catalog can answer.

    Args:
        query: Free text, e.g. "accounting", "MGMT 7307", "CPSC 5190",
            "Simonsohn", "Tuesday afternoon", "climate policy".
        school: Optional school filter, by name or code, e.g. "Management",
            "Yale College", "Public Health", "Environment", "MD".
            Leave empty to search every school.
        limit: Maximum rows to return (capped at 15).

    Returns:
        total_matches, returned, truncated and the matching course rows.
    """
    courses = load_courses()
    limit = max(1, min(int(limit or MAX_COURSE_RESULTS), MAX_COURSE_RESULTS))
    matched = find_courses(query, school=school, loose=True)

    result = CourseSearchResult(
        query=query or "",
        total_matches=len(matched),
        returned=min(len(matched), limit),
        truncated=len(matched) > limit,
        courses=[courses[i].summary() for i in matched[:limit]],
    )
    return result.model_dump()


def web_search(query: str, limit: int = MAX_WEB_RESULTS) -> dict:
    """Search the public web when the course catalog does not hold the answer.

    Use this for things outside data/yale_courses.json — faculty news,
    published research, syllabus context, programme requirements. Do not use it
    for course times, rooms or faculty assignments; those come from
    search_courses and must not be guessed.

    Args:
        query: What to look up on the public web.
        limit: Maximum results to return (capped at 5).

    Returns:
        The result list, each with title, url and snippet, or an error string.
    """
    limit = max(1, min(int(limit or MAX_WEB_RESULTS), MAX_WEB_RESULTS))
    cleaned = (query or "").strip()
    if not cleaned:
        return WebSearchResult(query="", error="Empty query.").model_dump()

    try:
        response = httpx.get(
            "https://html.duckduckgo.com/html/",
            params={"q": cleaned},
            headers={"User-Agent": "Mozilla/5.0 (course-explorer)"},
            timeout=20.0,
            follow_redirects=True,
        )
        response.raise_for_status()
    except Exception as exc:
        return WebSearchResult(
            query=cleaned, error=f"Web search unavailable: {type(exc).__name__}: {exc}"
        ).model_dump()

    results: list[WebResult] = []
    blocks = re.split(r'<div class="result[ "]', response.text)
    for block in blocks[1:]:
        link = re.search(r'<a[^>]+class="result__a"[^>]*href="([^"]+)"[^>]*>(.*?)</a>', block, re.S)
        if not link:
            continue
        snippet = re.search(r'class="result__snippet"[^>]*>(.*?)</a>', block, re.S)
        results.append(
            WebResult(
                title=_strip_tags(link.group(2)),
                url=html.unescape(link.group(1)),
                snippet=_strip_tags(snippet.group(1)) if snippet else "",
            )
        )
        if len(results) >= limit:
            break

    return WebSearchResult(
        query=cleaned, returned=len(results), results=results
    ).model_dump()


def _strip_tags(raw: str) -> str:
    return " ".join(html.unescape(re.sub(r"<[^>]+>", "", raw)).split())
