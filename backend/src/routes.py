from __future__ import annotations

from flask import Blueprint, jsonify, request

from src.services import catalog_service
from src.shared.errors import NotFoundError, ValidationError


api = Blueprint("api", __name__)


@api.get("/health")
def health_check():
    return jsonify({"data": {"status": "ok"}})


# ---------------------------------------------------------------------------
# Semesters
# ---------------------------------------------------------------------------

@api.get("/api/v1/semesters")
def list_semesters():
    semesters = catalog_service.list_semesters()
    return jsonify({"data": semesters})


# ---------------------------------------------------------------------------
# Course search
# ---------------------------------------------------------------------------

def _require_param(name: str) -> str:
    value = request.args.get(name, "").strip()
    if not value:
        raise ValidationError(
            f"'{name}' query parameter is required",
            details=[{"field": name, "issue": "missing"}],
        )
    return value


@api.get("/api/v1/courses/search")
def search_courses_v1():
    semester_id = _require_param("semesterId")
    query = _require_param("query")
    courses = catalog_service.search_courses(semester_id, query)

    if not courses:
        # Nothing in local cache — try to fetch live from KU and cache the result
        from src.catalog.on_demand import scrape_and_cache
        scrape_and_cache(query, semester_id)
        # Re-query the (now potentially updated) catalog
        courses = catalog_service.search_courses(semester_id, query)

    return jsonify({
        "data": courses,
        "meta": {"query": query, "semesterId": semester_id, "count": len(courses)},
    })


@api.get("/search")
def search_courses_alias():
    """Legacy alias — delegates to v1 handler."""
    return search_courses_v1()


# ---------------------------------------------------------------------------
# Course detail
# ---------------------------------------------------------------------------

@api.get("/api/v1/courses/<path:course_id>")
def get_course_by_id(course_id: str):
    semester_id = _require_param("semesterId")
    course = catalog_service.get_course_by_id(semester_id, course_id)
    if course is None:
        raise NotFoundError(f"Course '{course_id}' not found in semester '{semester_id}'")
    return jsonify({"data": course})


def register_routes(app) -> None:
    app.register_blueprint(api)
