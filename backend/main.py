"""Yale course explorer API desk (every school).

Run from Backend/: uvicorn main:app --reload --port 8000
Open API docs: http://127.0.0.1:8000/docs
Frontend (Vite): http://127.0.0.1:5173
"""

from __future__ import annotations

from collections import Counter

from dotenv import load_dotenv
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from pydantic import BaseModel, Field

from agent import run_agent
from tools import ROOT, data_path, find_courses, load_courses, load_rows

load_dotenv(ROOT / ".env")
load_dotenv(ROOT.parent / ".env")
load_dotenv(ROOT.parent.parent / ".env")

PAGE_SIZE = 48
MAX_PAGE_SIZE = 200
TERM_SEASONS = {"01": "Spring", "02": "Summer", "03": "Fall"}

app = FastAPI(title="Yale Courses", version="0.2.0")
app.add_middleware(GZipMiddleware, minimum_size=1000)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def term_label(code: str) -> str:
    """'202603' → 'Fall 2026'."""
    season = TERM_SEASONS.get(code[4:6]) if len(code) == 6 else None
    return f"{season} {code[:4]}" if season else code


class ChatRequest(BaseModel):
    message: str = Field(min_length=1)


class ChatResponse(BaseModel):
    reply: str
    tools_used: list[str] = Field(default_factory=list)


@app.get("/api/health")
def health():
    return {"ok": True, "courses_file": data_path().name, "courses": len(load_rows())}


@app.get("/api/schools")
def list_schools():
    """Each school with its course count and categories, for the filters."""
    courses = load_courses()
    by_school: dict[tuple[str, str], Counter] = {}
    for c in courses:
        by_school.setdefault((c.school_code, c.school), Counter())[c.category.strip()] += 1
    terms = Counter(c.term_code for c in courses if c.term_code)
    term = terms.most_common(1)[0][0] if terms else ""
    schools = [
        {
            "code": code,
            "name": name,
            "count": sum(cats.values()),
            "categories": sorted(k for k in cats if k),
        }
        for (code, name), cats in sorted(by_school.items(), key=lambda item: item[0][1])
    ]
    return {"term": term_label(term), "total": len(courses), "schools": schools}


@app.get("/api/courses")
def list_courses(
    q: str | None = Query(default=None, description="Search words; every word must match"),
    school: str | None = Query(default=None, description="School code, e.g. MG or YC"),
    category: str | None = Query(default=None),
    offset: int = Query(default=0, ge=0),
    limit: int = Query(default=PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
):
    """One page of matching courses for the React catalog."""
    rows = load_rows()
    matched = find_courses(q or "", school=school or "", category=category or "")
    page = matched[offset : offset + limit]
    return {
        "count": len(matched),
        "total": len(rows),
        "offset": offset,
        "limit": limit,
        "courses": [rows[i] for i in page],
    }


@app.post("/api/chat", response_model=ChatResponse)
def chat(body: ChatRequest):
    result = run_agent(body.message)
    return ChatResponse(
        reply=result.get("reply", ""),
        tools_used=list(result.get("tools_used") or []),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=False)
