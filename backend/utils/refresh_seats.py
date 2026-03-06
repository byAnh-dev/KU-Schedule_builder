"""
Refresh seat availability from KU's live course search.

Reads all subjects from courseDatabase.json, scrapes KU for current seat
counts per subject, and writes CRN -> seatAvailable to seats.json.

The running server reloads seats.json automatically every 5 minutes, so
no restart is needed after this script runs.

Cron example (hourly):
    0 * * * * cd /home/ubuntu/KU-Schedule_builder && \
        python backend/utils/refresh_seats.py >> /var/log/ku-seats.log 2>&1
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from bs4 import BeautifulSoup

_BACKEND_DIR = Path(__file__).parent.parent
_DB_PATH = _BACKEND_DIR / "courseDatabase.json"
_SEATS_PATH = _BACKEND_DIR / "seats.json"

SEARCH_URL = "https://classes.ku.edu/Classes/CourseSearch.action"

_SECTION_TYPES = {
    "LEC", "LBN", "DIS", "LAB", "IND", "FLD",
    "RSH", "CLN", "ACT", "INT", "SEM", "PRA", "STU", "WKS", "THE",
}

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/133.0.0.0 Safari/537.36"
    ),
    "Content-Type": "application/x-www-form-urlencoded",
    "X-Requested-With": "XMLHttpRequest",
}


def _subjects_by_term() -> dict[str, list[str]]:
    """Return {term_code: [subject, ...]} extracted from courseDatabase.json."""
    with open(_DB_PATH, encoding="utf-8") as f:
        payload = json.load(f)

    if isinstance(payload, dict) and "semesters" in payload:
        raw_by_term = payload["semesters"]
    elif isinstance(payload, dict) and "term" in payload:
        raw_by_term = {payload["term"]: payload.get("courses", [])}
    else:
        raw_by_term = {"4262": payload if isinstance(payload, list) else []}

    result: dict[str, list[str]] = {}
    for term_code, courses in raw_by_term.items():
        subjects: set[str] = set()
        for course in courses:
            raw_id = course.get("id", "").strip()
            if raw_id:
                subjects.add(raw_id.split()[0].upper())
        result[term_code] = sorted(subjects)
    return result


def _parse_seats(html: str) -> dict[str, int | str]:
    """Extract {crn: seatAvailable} from KU search results HTML."""
    soup = BeautifulSoup(html, "html.parser")
    seats: dict[str, int | str] = {}
    if not soup.table:
        return seats
    for row in soup.table.find_all("tr"):
        cols = row.find_all("td")
        if len(cols) < 5:
            continue
        if cols[0].get_text(strip=True) not in _SECTION_TYPES:
            continue
        crn_tag = cols[3].find("strong")
        if not crn_tag:
            continue
        crn = crn_tag.get_text(strip=True)
        seat_text = cols[4].get_text(strip=True)
        if seat_text.upper() in ("FULL", "CLOSED"):
            seats[crn] = "Full"
        else:
            try:
                seats[crn] = int(seat_text)
            except ValueError:
                pass
    return seats


def _scrape(subject: str, term_code: str) -> dict[str, int | str]:
    form_data = {
        "classesSearchText": subject,
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
        resp = requests.post(SEARCH_URL, data=form_data, headers=_HEADERS, timeout=30)
        resp.raise_for_status()
        return _parse_seats(resp.text)
    except Exception as exc:
        print(f"  [warn] {subject} term={term_code}: {exc}", file=sys.stderr)
        return {}


def main() -> None:
    subjects_by_term = _subjects_by_term()
    total = sum(len(s) for s in subjects_by_term.values())
    all_seats: dict[str, int | str] = {}
    done = 0

    for term_code, subjects in subjects_by_term.items():
        for subject in subjects:
            done += 1
            print(f"[{done}/{total}] {subject} (term {term_code})...", end=" ", flush=True)
            seats = _scrape(subject, term_code)
            all_seats.update(seats)
            print(f"{len(seats)} CRNs")
            time.sleep(1)  # be polite to KU's servers

    all_seats["_updated"] = datetime.now(timezone.utc).isoformat()

    # Write atomically via temp file so the server never reads a partial file
    tmp = _SEATS_PATH.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(all_seats, f, ensure_ascii=False)
    tmp.replace(_SEATS_PATH)

    print(f"\nDone. Wrote {len(all_seats) - 1} CRN seat records to {_SEATS_PATH}")


if __name__ == "__main__":
    main()
