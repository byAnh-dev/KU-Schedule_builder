import pytest
from src.catalog.loader import load_catalog, get_semesters, search_courses, get_course_by_id


@pytest.fixture(scope="module", autouse=True)
def catalog():
    load_catalog()


# ---------------------------------------------------------------------------
# Semesters
# ---------------------------------------------------------------------------

def test_semesters_non_empty():
    sems = get_semesters()
    assert len(sems) >= 1

def test_semester_shape():
    sem = get_semesters()[0]
    assert "id" in sem and "label" in sem
    assert sem["id"]   # non-empty
    assert sem["label"]

def test_semester_id_format():
    # Should be "YYYYsS" pattern like "2025SP"
    sem_id = get_semesters()[0]["id"]
    assert len(sem_id) == 6
    assert sem_id[:4].isdigit()
    assert sem_id[4:] in ("SP", "SU", "FA")


# ---------------------------------------------------------------------------
# search_courses
# ---------------------------------------------------------------------------

def test_search_returns_list():
    sem_id = get_semesters()[0]["id"]
    results = search_courses(sem_id, "eecs")
    assert isinstance(results, list)

def test_search_substring_match():
    sem_id = get_semesters()[0]["id"]
    results = search_courses(sem_id, "EECS")
    assert all("EECS" in c["id"] for c in results)

def test_search_case_insensitive():
    sem_id = get_semesters()[0]["id"]
    lower = search_courses(sem_id, "eecs")
    upper = search_courses(sem_id, "EECS")
    assert {c["id"] for c in lower} == {c["id"] for c in upper}

def test_search_whitespace_collapsed():
    sem_id = get_semesters()[0]["id"]
    with_space = search_courses(sem_id, "EECS 1")
    without_space = search_courses(sem_id, "EECS1")
    assert {c["id"] for c in with_space} == {c["id"] for c in without_space}

def test_search_wrong_semester_empty():
    results = search_courses("NONEXISTENT", "eecs")
    assert results == []


# ---------------------------------------------------------------------------
# Course shape
# ---------------------------------------------------------------------------

def test_course_required_fields():
    sem_id = get_semesters()[0]["id"]
    results = search_courses(sem_id, "aaas")
    assert results, "Expected at least one AAAS course"
    course = results[0]
    for field in ("id", "subject", "number", "title", "semesterId", "components"):
        assert field in course, f"Missing field: {field}"

def test_course_id_format():
    sem_id = get_semesters()[0]["id"]
    results = search_courses(sem_id, "aaas")
    assert results
    course = results[0]
    # id should be "SUBJECT NUMBER" with single space
    parts = course["id"].split(" ")
    assert len(parts) == 2
    assert parts[0] == parts[0].upper()

def test_course_semester_id_matches():
    sem_id = get_semesters()[0]["id"]
    results = search_courses(sem_id, "eecs")
    for course in results:
        assert course["semesterId"] == sem_id

def test_component_shape():
    sem_id = get_semesters()[0]["id"]
    results = search_courses(sem_id, "aaas")
    assert results
    course = results[0]
    if course["components"]:
        comp = course["components"][0]
        for field in ("id", "type", "section", "meetings"):
            assert field in comp, f"Missing component field: {field}"
        assert comp["type"] in ("LEC", "LAB", "DIS", "REC")

def test_component_type_no_lbn():
    """LBN sections must be mapped to LAB, never appear as LBN."""
    sem_id = get_semesters()[0]["id"]
    for course in search_courses(sem_id, ""):
        for comp in course["components"]:
            assert comp["type"] != "LBN"

def test_meeting_shape():
    sem_id = get_semesters()[0]["id"]
    results = search_courses(sem_id, "eecs")
    for course in results:
        for comp in course["components"]:
            for meeting in comp["meetings"]:
                assert "days" in meeting
                assert "startTime" in meeting
                assert "endTime" in meeting
                assert isinstance(meeting["days"], list)
                assert all(d in ("M", "T", "W", "Th", "F", "Sa", "Su") for d in meeting["days"])

def test_no_t_th_confusion():
    """Ensure 'T' (Tuesday) and 'Th' (Thursday) are never confused."""
    sem_id = get_semesters()[0]["id"]
    for course in search_courses(sem_id, ""):
        for comp in course["components"]:
            for meeting in comp["meetings"]:
                for day in meeting["days"]:
                    assert day in ("M", "T", "W", "Th", "F", "Sa", "Su"), f"Invalid day: {day!r}"


# ---------------------------------------------------------------------------
# get_course_by_id
# ---------------------------------------------------------------------------

def test_get_course_by_id_found():
    sem_id = get_semesters()[0]["id"]
    results = search_courses(sem_id, "aaas")
    assert results
    course_id = results[0]["id"]
    found = get_course_by_id(sem_id, course_id)
    assert found is not None
    assert found["id"] == course_id

def test_get_course_by_id_not_found():
    sem_id = get_semesters()[0]["id"]
    assert get_course_by_id(sem_id, "FAKE 999") is None

def test_get_course_by_id_wrong_semester():
    sem_id = get_semesters()[0]["id"]
    results = search_courses(sem_id, "aaas")
    assert results
    course_id = results[0]["id"]
    assert get_course_by_id("NONEXISTENT", course_id) is None
