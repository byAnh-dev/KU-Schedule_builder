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

# Fallback term code if the JSON file doesn't embed one.
# Override via KU_TERM_CODE env var or by re-scraping (which embeds the term).
_DEFAULT_TERM_CODE = os.environ.get("KU_TERM_CODE", "4262")

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


def _parse_seat_available(raw: Any) -> int | str | None:
    """Parse seatAvailable: numeric string → int, 'Full' → 'Full', else None."""
    if raw is None:
        return None
    s = str(raw).strip()
    if s.upper() in {"FULL", "CLOSED"}:
        return "Full"
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


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
    """Transform one raw scraped course dict into the frontend Course shape."""
    code = _normalise_course_code(raw.get("id"))
    if not code:
        return None

    parts = code.split(" ", 1)
    subject = parts[0]
    number = parts[1] if len(parts) > 1 else ""

    credits_raw = raw.get("credits")
    credits: int | None = None
    try:
        credits = int(credits_raw) if credits_raw is not None else None
    except (ValueError, TypeError):
        pass

    desc = _null(raw.get("description"))
    prereq = _null(raw.get("prerequisite"))

    # Build components from the scraped components list, grouped by type
    # so we can assign sequential labels (001, 002 … / L01, L02 …).
    raw_components: list[dict[str, Any]] = raw.get("components") or []
    by_type: dict[str, list[dict[str, Any]]] = {}
    for comp in raw_components:
        sec_type = _map_section_type(comp.get("type"))
        by_type.setdefault(sec_type, []).append(comp)

    components: list[dict[str, Any]] = []
    for sec_type, group in sorted(by_type.items()):
        for idx, comp in enumerate(group, start=1):
            label = _generate_section_label(idx, sec_type)
            comp_id = f"{code}-{sec_type}-{label}"
            meetings = parse_meeting_time(comp.get("meetingTime"))
            components.append(
                {
                    "id": comp_id,
                    "type": sec_type,
                    "section": label,
                    "meetings": meetings,
                    "instructor": _null(comp.get("instructor")),
                    "location": _null(comp.get("location")),
                    "seatAvailable": _parse_seat_available(comp.get("seatAvailable")),
                    "crn": _null(comp.get("id")),
                }
            )

    course: dict[str, Any] = {
        "id": code,
        "subject": subject,
        "number": number,
        "title": _null(raw.get("title")) or code,
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

    Supported JSON formats (all three are handled for backwards compatibility):
      1. {"semesters": {"4262": [...], "4266": [...]}}  ← multi-term (current)
      2. {"term": "4262", "courses": [...]}              ← single-term
      3. [...]                                           ← legacy bare list
    """
    global _catalog, _search_index, _semesters

    with open(_DB_PATH, encoding="utf-8") as f:
        payload = json.load(f)

    # Normalise to {term_code: [raw_courses]} regardless of format.
    if isinstance(payload, dict) and "semesters" in payload:
        raw_by_term: dict[str, list] = payload["semesters"]
    elif isinstance(payload, dict) and "term" in payload:
        raw_by_term = {payload["term"]: payload.get("courses", [])}
    else:
        raw_by_term = {_DEFAULT_TERM_CODE: payload if isinstance(payload, list) else []}

    new_catalog: dict[str, list[dict[str, Any]]] = {}
    new_search_index: dict[str, list[tuple[str, dict[str, Any]]]] = {}
    new_semesters: list[dict[str, str]] = []

    # Sort by term code so semesters appear in chronological order.
    for term_code in sorted(raw_by_term.keys()):
        semester_id = term_code_to_semester_id(term_code)
        label = term_code_to_label(term_code)

        courses: list[dict[str, Any]] = []
        for raw in raw_by_term[term_code]:
            course = _transform_course(raw, semester_id)
            if course:
                courses.append(course)

        new_catalog[semester_id] = courses
        new_search_index[semester_id] = [
            (c["id"].replace(" ", "").lower(), c) for c in courses
        ]
        new_semesters.append({"id": semester_id, "label": label})

    _catalog = new_catalog
    _search_index = new_search_index
    _semesters = new_semesters


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
