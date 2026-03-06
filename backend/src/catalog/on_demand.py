"""
On-demand course scraper.

Triggered when a local search returns no results. Makes a direct HTTP POST
to the KU course search endpoint (no Playwright required — the endpoint is
publicly accessible). If a saved auth state is present, cookies are attached
so instructor names and locations are included in the response.

Newly found courses are merged into the in-memory catalog and persisted to
courseDatabase.json so they are available on future requests without
re-scraping.
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any

import requests
from bs4 import BeautifulSoup

from src.catalog.loader import get_term_code, merge_raw_courses

# ---------------------------------------------------------------------------
# Constants (mirrors utils/course_scraper.py)
# ---------------------------------------------------------------------------

_BACKEND_DIR = Path(__file__).parent.parent.parent
AUTH_STATE_PATH = _BACKEND_DIR / "auth" / "browser_state.json"
SEARCH_URL = "https://classes.ku.edu/Classes/CourseSearch.action"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
}

# Queries confirmed to return no results — skip re-scraping them.
# Key: "{semester_id}:{normalised_query}"
_not_found_cache: set[str] = set()


# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def _load_cookies() -> dict[str, str]:
    """
    Extract cookies from the saved Playwright browser state JSON.
    Returns an empty dict if the file is missing or unreadable.
    """
    if not AUTH_STATE_PATH.exists():
        return {}
    try:
        state = json.loads(AUTH_STATE_PATH.read_text(encoding="utf-8"))
        return {c["name"]: c["value"] for c in state.get("cookies", []) if c.get("name")}
    except Exception:
        return {}


# ---------------------------------------------------------------------------
# HTML parser (no Playwright dependency — pure BeautifulSoup)
# Kept in sync with utils/course_scraper.py _parse_html()
# ---------------------------------------------------------------------------

def _parse_html(html: str) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    if not soup.table:
        return []

    rows = soup.table.find_all("tr", class_=None, id_=None)
    course_list: list[dict] = []
    course: dict = {}
    i = 1

    for row in rows:
        section_list: list[dict] = []
        try:
            if i % 5 == 1:
                if row.h3:
                    raw_code = row.h3.get_text(strip=True)
                    parts = raw_code.split(" ", 1)
                    course["id"] = raw_code
                    course["subject"] = parts[0] if parts else ""
                    course["number"] = parts[1] if len(parts) > 1 else ""

                other = row.td.contents[2].get_text(strip=True).split("\n")
                course["title"] = other[0].strip()
                credits_raw = other[3].strip() if len(other) > 3 else ""
                course["credits"] = int(credits_raw) if credits_raw.isdigit() else credits_raw

                if len(other) == 9:
                    course["semesterId"] = other[8].strip()
                    course["honors"] = False
                elif len(other) == 11:
                    course["semesterId"] = other[10].strip()
                    course["honors"] = True
                else:
                    course["semesterId"] = ""
                    course["honors"] = False

            elif i % 5 == 2:
                text = row.td.get_text(strip=True)
                description = text
                if "Prerequisite:" in text:
                    description = text.split("Prerequisite:")[0].strip()
                if "Satisfies:" in text:
                    description = description.split("Satisfies:")[0].strip()
                course["description"] = description

                prerequisite = "N/A"
                if "Prerequisite:" in text:
                    prerequisite = text.split("Prerequisite:")[1].split("\n")[0].strip()
                    if "Satisfies:" in prerequisite:
                        prerequisite = prerequisite.split("Satisfies:")[0].rstrip(". ").strip()
                    if "Corequisite" in prerequisite:
                        try:
                            prerequisite = prerequisite.split("Corequisite")[1].strip()
                        except Exception:
                            pass
                course["prerequisite"] = prerequisite

                corequisite = "N/A"
                if "Corequisite:" in text:
                    corequisite = text.split("Corequisite:")[1].split("\n")[0].strip()
                course["corequisite"] = corequisite

                satisfies = "N/A"
                if "Satisfies:" in text:
                    goal_string = text.split("Satisfies:")[1].strip()
                    goals = goal_string.split(",")
                    cleaned = []
                    for goal in goals:
                        words = [w.strip() for w in goal.split("\n") if w.strip()]
                        cleaned.append(" ".join(words))
                    satisfies = " & ".join(cleaned)
                course["satisfies"] = satisfies

            elif i % 5 == 3:
                if not row.table:
                    course["components"] = []
                    i += 1
                    continue

                section_rows = row.table.find_all("tr")
                current_section: dict = {}
                current_id = ""

                for sec_row in section_rows:
                    cols = sec_row.find_all("td")
                    if len(cols) < 2:
                        continue
                    col0 = cols[0].get_text(strip=True)

                    if col0 in ("LEC", "LBN", "DIS", "LAB", "IND", "FLD", "RSH", "CLN", "ACT", "INT", "SEM", "PRA", "STU", "WKS", "THE"):
                        instructor_tag = cols[1].find("a")
                        instructor = instructor_tag.get_text(strip=True) if instructor_tag else "N/A"
                        crn_tag = cols[3].find("strong") if len(cols) > 3 else None
                        if not crn_tag:
                            current_section = {}
                            current_id = ""
                            continue
                        current_id = crn_tag.get_text(strip=True)
                        seat_available = cols[4].get_text(strip=True) if len(cols) > 4 else "Unopened"
                        current_section = {
                            "id": current_id,
                            "type": col0,
                            "instructor": instructor,
                            "seatAvailable": seat_available,
                        }

                    elif "Notes" in col0 and current_id:
                        location = "OFF CMPS-K"
                        loc_tag = cols[1].span
                        if loc_tag:
                            if not (loc_tag.find("img") or loc_tag.get_text() == ""):
                                loc_text = loc_tag.string.strip() if loc_tag.string else ""
                                if loc_text == "ONLNE CRSE":
                                    location = "Online"
                                elif loc_text == "KULC APPT":
                                    location = "By Appointment"
                                else:
                                    campus = ""
                                    n_contents = len(cols[1].contents)
                                    if n_contents == 11:
                                        campus = cols[1].contents[6].get_text(strip=True)
                                    elif n_contents == 15:
                                        campus = cols[1].contents[12].get_text(strip=True)
                                    location = f"{loc_text} {campus}".strip()

                        date_parts = cols[1].contents[0].get_text(strip=True).split("\n")
                        date_parts = [d.strip() for d in date_parts]
                        meeting_time = None
                        if len(date_parts) > 2:
                            date_parts.pop(2)
                            meeting_time = " ".join(date_parts)
                        elif date_parts and date_parts[0] == "APPT":
                            try:
                                meeting_time = cols[1].find("strong").string
                            except Exception:
                                meeting_time = None

                        current_section["meetingTime"] = meeting_time
                        current_section["location"] = location
                        section_list.append(current_section.copy())
                        current_section = {}
                        current_id = ""

                course["components"] = section_list

            elif i % 5 == 0:
                if course.get("satisfies") and course["satisfies"] != "N/A":
                    course["satisfied"] = [s.strip() for s in course["satisfies"].split(" & ")]
                course_list.append(course.copy())
                course.clear()

        except Exception as exc:
            print(f"[on_demand] Parse error at row {i}: {exc}")

        i += 1

    return course_list


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def _fetch_raw(query: str, term_code: str, cookies: dict) -> list[dict[str, Any]]:
    form_data = {
        "classesSearchText": query,
        "searchCareer": "UndergraduateGraduate",
        "searchTerm": term_code,
        "searchSchool": "",
        "searchDept": "",
        "searchSubject": "",
        "searchCode": "",
        "textbookOptions": "",
        "searchCampus": "",
        "searchBuilding": "",
        "searchCourseNumberMin": "001",
        "searchCourseNumberMax": "999",
        "searchCreditHours": "",
        "searchInstructor": "",
        "searchStartTime": "",
        "searchEndTime": "",
        "searchClosed": "false",
        "searchHonorsClasses": "false",
        "searchShortClasses": "false",
        "searchOnlineClasses": "",
        "searchIncludeExcludeDays": "include",
        "searchDays": "",
    }
    try:
        resp = requests.post(
            SEARCH_URL,
            data=form_data,
            cookies=cookies or None,
            headers=_HEADERS,
            timeout=20,
        )
        resp.raise_for_status()
        return _parse_html(resp.text)
    except Exception as exc:
        print(f"[on_demand] HTTP request failed for {query!r}: {exc}")
        return []


def scrape_and_cache(query: str, semester_id: str) -> list[dict[str, Any]]:
    """
    Query the KU live catalog for `query` in `semester_id`.

    - Returns immediately with [] if the query was previously confirmed empty.
    - Detects graduate vs undergraduate career from the course number.
    - Newly found courses are merged into the catalog and persisted to disk.
    - Returns the list of newly added transformed courses.
    """
    cache_key = f"{semester_id}:{query.replace(' ', '').lower()}"
    if cache_key in _not_found_cache:
        return []

    term_code = get_term_code(semester_id)
    if not term_code:
        return []

    cookies = _load_cookies()
    raw_courses = _fetch_raw(query, term_code, cookies)

    if not raw_courses:
        _not_found_cache.add(cache_key)
        return []

    added = merge_raw_courses(raw_courses, semester_id, term_code)
    if not added:
        _not_found_cache.discard(cache_key)
    return added
