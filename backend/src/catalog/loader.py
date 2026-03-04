from __future__ import annotations

import json
import os
import re
from typing import Any

from src.catalog.meeting_parser import parse_meeting_time
from src.catalog.semesters import term_code_to_label, term_code_to_semester_id

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_DB_PATH = os.path.join(_BACKEND_DIR, "courseDatabase.json")

# Term code for the scraped dataset. Change this when a new scrape is done.
_TERM_CODE = "4252"  # Spring 2025

# ---------------------------------------------------------------------------
# In-memory store (populated once at startup)
# ---------------------------------------------------------------------------

# { semester_id: [course_dict, ...] }
_catalog: dict[str, list[dict[str, Any]]] = {}

# { semester_id: [(normalised_id, course_dict), ...] }  for fast search
_search_index: dict[str, list[tuple[str, dict[str, Any]]]] = {}

# [{"id": ..., "label": ...}]
_semesters: list[dict[str, str]] = []


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

_SECTION_TYPE_MAP: dict[str, str] = {
    "LEC": "LEC",
    "LAB": "LAB",
    "DIS": "DIS",
    "REC": "REC",
    "LBN": "LAB",  # lab-lecture combined -> treat as LAB
    "IND": "LEC",  # independent/directed study -> treat as LEC
    "FLD": "LEC",  # field study -> treat as LEC
    "RSH": "LEC",  # rehearsal -> treat as LEC
    "CLN": "LEC",  # clinical -> treat as LEC
    "ACT": "LEC",  # activity -> treat as LEC
    "INT": "LEC",  # internship -> treat as LEC
    "SEM": "LEC",  # seminar -> treat as LEC
    "PRA": "LEC",  # practicum -> treat as LEC
    "STU": "LEC",  # studio -> treat as LEC
    "WKS": "LEC",  # workshop -> treat as LEC
}


def _map_section_type(raw: str | None) -> str:
    return _SECTION_TYPE_MAP.get((raw or "").strip().upper(), "LEC")


def _normalise_course_code(raw: str | None) -> str:
    """Collapse whitespace and uppercase the subject portion."""
    if not raw:
        return ""
    collapsed = re.sub(r"\s+", " ", raw.strip())
    m = re.match(r"^([A-Za-z&]+)\s+(\S+)$", collapsed)
    if m:
        return f"{m.group(1).upper()} {m.group(2)}"
    return collapsed.upper()


def _null(value: Any) -> Any:
    """Convert N/A-style strings to None."""
    if value is None:
        return None
    s = str(value).strip()
    if s.upper() in {"N/A", "NA", "NONE", "NULL", ""}:
        return None
    return s


def _generate_section_label(index: int, sec_type: str) -> str:
    """
    Generate a human-readable section label.
    LEC sections get "001", "002", …
    LAB/DIS/REC get "L01", "D01", "R01", …
    """
    prefix_map = {"LEC": "", "LAB": "L", "DIS": "D", "REC": "R"}
    prefix = prefix_map.get(sec_type, "")
    width = 2 if prefix else 3
    return f"{prefix}{index:0{width}d}"


def _transform_course(raw: dict[str, Any], semester_id: str) -> dict[str, Any] | None:
    """Transform one raw course dict into the frontend Course shape."""
    code = _normalise_course_code(raw.get("CourseCode"))
    if not code:
        return None

    # Split "SUBJECT NUMBER" into parts
    parts = code.split(" ", 1)
    subject = parts[0]
    number = parts[1] if len(parts) > 1 else ""

    # Parse credits
    credits_raw = _null(raw.get("CreditHours"))
    credits: int | None = None
    if credits_raw and str(credits_raw).isdigit():
        credits = int(credits_raw)

    # Clean description and prerequisites (strip "Prerequisite:" / "Satisfies:" prefixes)
    desc = _null(raw.get("CourseDescription"))
    prereq = _null(raw.get("Prerequisite"))

    # Build components from Sections dict
    sections_raw: dict[str, Any] = raw.get("Sections") or {}

    # Group by type to assign sequential labels per type
    by_type: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    for crn, sec in sections_raw.items():
        sec_type = _map_section_type(sec.get("SectionType"))
        by_type.setdefault(sec_type, []).append((crn, sec))

    # Sort each type group by CRN for deterministic ordering
    for sec_type in by_type:
        by_type[sec_type].sort(key=lambda t: t[0])

    components: list[dict[str, Any]] = []
    for sec_type, group in sorted(by_type.items()):
        for idx, (crn, sec) in enumerate(group, start=1):
            label = _generate_section_label(idx, sec_type)
            comp_id = f"{code}-{sec_type}-{label}"
            meetings = parse_meeting_time(sec.get("MeetingTime"))
            components.append(
                {
                    "id": comp_id,
                    "type": sec_type,
                    "section": label,
                    "meetings": meetings,
                    "instructor": _null(sec.get("Instructor")),
                    "location": _null(sec.get("Location")),
                }
            )

    course: dict[str, Any] = {
        "id": code,
        "subject": subject,
        "number": number,
        "title": _null(raw.get("CourseName")) or code,
        "semesterId": semester_id,
        "components": components,
    }
    if desc:
        course["description"] = desc
    if prereq:
        course["prerequisites"] = prereq
    if credits is not None:
        course["credits"] = credits

    return course


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_catalog() -> None:
    """
    Load and transform courseDatabase.json into the in-memory catalog.
    Idempotent — safe to call multiple times (re-reads and replaces the store).
    """
    global _catalog, _search_index, _semesters

    semester_id = term_code_to_semester_id(_TERM_CODE)
    label = term_code_to_label(_TERM_CODE)

    with open(_DB_PATH, encoding="utf-8") as f:
        raw_data: list[dict[str, Any]] = json.load(f)

    courses: list[dict[str, Any]] = []
    for raw in raw_data:
        course = _transform_course(raw, semester_id)
        if course:
            courses.append(course)

    _catalog = {semester_id: courses}
    _search_index = {
        semester_id: [
            (c["id"].replace(" ", "").lower(), c) for c in courses
        ]
    }
    _semesters = [{"id": semester_id, "label": label}]


def get_semesters() -> list[dict[str, str]]:
    return list(_semesters)


def search_courses(semester_id: str, query: str) -> list[dict[str, Any]]:
    """
    Filter courses by semester + normalised course-ID substring.
    Matches frontend behaviour: collapse whitespace, lowercase, substring match.
    """
    normalised_query = query.replace(" ", "").lower()
    index = _search_index.get(semester_id, [])
    return [course for norm_id, course in index if normalised_query in norm_id]


def get_course_by_id(semester_id: str, course_id: str) -> dict[str, Any] | None:
    """Exact lookup by semester + course ID (e.g. "EECS 388")."""
    for course in _catalog.get(semester_id, []):
        if course["id"] == course_id:
            return course
    return None
