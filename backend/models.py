"""Pydantic models for the Yale course explorer.

Field aliases match the exact keys in data/yale_courses.json (the SOM listing's
keys plus School fields), so a raw row validates with Course.model_validate(row)
and nothing has to be renamed by hand.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class Course(BaseModel):
    """One row of data/yale_courses.json."""

    model_config = ConfigDict(populate_by_name=True, extra="ignore")

    course_id: str = Field(default="", alias="Course ID")
    number: str = Field(default="", alias="Course Number")
    title: str = Field(default="", alias="Course Title")
    category: str = Field(default="", alias="Course Category")
    course_type: str = Field(default="", alias="Course Type")
    section: str = Field(default="", alias="Section")
    units: str = Field(default="", alias="Units")

    description: str = Field(default="", alias="Course Description")

    faculty: str = Field(default="", alias="Faculty 1")
    faculty_email: str = Field(default="", alias="Faculty 1 Email")
    faculty_bio: str = Field(default="", alias="faculty_bio")

    daytimes: str = Field(default="", alias="Daytimes")
    day: str = Field(default="", alias="Timings Day")
    start_time: str = Field(default="", alias="Timings StartTime")
    end_time: str = Field(default="", alias="Timings EndTime")
    room: str = Field(default="", alias="Room")

    session: str = Field(default="", alias="Course Session")
    session_start: str = Field(default="", alias="Course Session Start date")
    session_end: str = Field(default="", alias="Course Session End Date")
    term_code: str = Field(default="", alias="TermCode")

    bid_or_permission: str = Field(default="", alias="Bid Or Permission")
    syllabus: str = Field(default="", alias="Syllabus")
    old_syllabus: str = Field(default="", alias="Old Syllabus")
    visible: str = Field(default="", alias="Visible")

    school: str = Field(default="School of Management", alias="School")
    school_code: str = Field(default="MG", alias="School Code")
    subject: str = Field(default="", alias="Subject")
    same_as: str = Field(default="", alias="Same As")
    source_url: str = Field(default="", alias="Source URL")
    sections: int = Field(default=1, alias="Sections")

    def haystack(self) -> str:
        """Everything a text query may legitimately match against.

        School and units stay out: school is its own filter, and "Yale College"
        or "Arts & Sciences" would otherwise match thousands of rows.
        """
        return " ".join(
            [
                self.number,
                self.same_as,
                self.title,
                self.category,
                self.course_type,
                self.faculty,
                self.faculty_email,
                self.daytimes,
                self.day,
                self.start_time,
                self.end_time,
                self.room,
                self.session,
                self.bid_or_permission,
                self.description,
                self.faculty_bio,
            ]
        ).lower()

    def summary(self, description_chars: int = 500) -> dict[str, Any]:
        """Compact shape handed to the model — trimmed, never invented."""
        desc = " ".join(self.description.split())
        bio = " ".join(self.faculty_bio.split())
        return {
            "school": self.school,
            "number": self.number,
            "same_as": self.same_as,
            "title": self.title,
            "category": self.category,
            "faculty": self.faculty,
            "faculty_email": self.faculty_email.strip(),
            "daytimes": self.daytimes,
            "room": self.room,
            "units": self.units,
            "session": self.session,
            "sections": self.sections,
            "bid_or_permission": self.bid_or_permission,
            "syllabus": self.syllabus or self.old_syllabus,
            "course_search_url": self.source_url,
            "description": desc[:description_chars],
            "faculty_bio": bio[:description_chars],
        }


class CourseSearchResult(BaseModel):
    """What search_courses hands back to the agent."""

    query: str
    total_matches: int
    returned: int
    truncated: bool = False
    courses: list[dict[str, Any]] = Field(default_factory=list)


class WebResult(BaseModel):
    """A single public-web hit."""

    title: str = ""
    url: str = ""
    snippet: str = ""


class WebSearchResult(BaseModel):
    """What web_search hands back to the agent."""

    query: str
    returned: int = 0
    results: list[WebResult] = Field(default_factory=list)
    error: str = ""


class ToolRecord(BaseModel):
    """One tool call as recorded for the audit trail."""

    name: str
    args: Any = None
    result_preview: str = ""


class AuditEntry(BaseModel):
    """One agent loop, appended to output/audit_trail.json."""

    time: str
    user_message: str
    thoughts: list[str] = Field(default_factory=list)
    tools: list[ToolRecord] = Field(default_factory=list)
    reply: str = ""
    stop_reason: str = ""
    model: str = ""


class AgentResult(BaseModel):
    """The contract main.py depends on."""

    reply: str
    tools_used: list[str] = Field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return {"reply": self.reply, "tools_used": list(self.tools_used)}
