from __future__ import annotations

from typing import Any

from src.catalog import loader


def list_semesters() -> list[dict[str, str]]:
    """Return all available semesters."""
    return loader.get_semesters()


def search_courses(semester_id: str, query: str) -> list[dict[str, Any]]:
    """
    Filter courses by semester + normalised course-ID substring.

    Matches frontend behaviour: collapse whitespace, lowercase, substring match
    on the course ID (e.g. query "eecs38" matches "EECS 388").
    """
    return loader.search_courses(semester_id, query)


def get_course_by_id(semester_id: str, course_id: str) -> dict[str, Any] | None:
    """Exact lookup by semester + course ID (e.g. "EECS 388")."""
    return loader.get_course_by_id(semester_id, course_id)
