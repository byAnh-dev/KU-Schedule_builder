"""
KU course scraper — Playwright edition with saved login state.

Flow
----
First run (or when session expires):
    python course_scraper.py --login
    A visible browser opens. Log in through KU SSO normally.
    The script detects the redirect back to classes.ku.edu and saves
    the browser state (cookies + localStorage) to AUTH_STATE_PATH.

Subsequent runs:
    python course_scraper.py
    Headless browser reuses the saved state to POST the search form
    and parse the HTML response. No login required.

If the saved session has expired the scraper will print a warning and
exit with a non-zero code — re-run with --login to refresh it.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path
from urllib.parse import urlencode

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEARCH_URL = "https://classes.ku.edu/Classes/CourseSearch.action"
LOGIN_URL  = "https://classes.ku.edu/Classes/Login.action"

# Where the saved browser state lives.  Not committed to git.
AUTH_STATE_PATH = Path(__file__).parent.parent / "auth" / "browser_state.json"

DEFAULT_FORM = {
    "classesSearchText": "",
    "searchCareer": "Undergraduate",
    "searchTerm": "4252",          # Spring 2025 — change per term
    "searchCourseNumberMin": "001",
    "searchCourseNumberMax": "999",
    "searchClosed": "true",
    "searchHonorsClasses": "false",
    "searchShortClasses": "false",
    "searchIncludeExcludeDays": "include",
}

# ---------------------------------------------------------------------------
# Auth helpers
# ---------------------------------------------------------------------------

def login_and_save_state(state_path: Path) -> None:
    """
    Open a visible browser, let the user complete KU SSO login, then save
    the session state to disk so future runs can skip the login step.
    """
    state_path.parent.mkdir(parents=True, exist_ok=True)

    state_path.parent.mkdir(parents=True, exist_ok=True)

    print("Opening browser…")
    print()
    print(f"  --> Paste this URL into the browser if it doesn't load:")
    print(f"      {LOGIN_URL}")
    print()
    print("Log in through KU SSO. The script saves state automatically")
    print("once the login completes (you have 5 minutes).\n")

    with sync_playwright() as p:
        # Try real Chrome first; fall back to bundled Chromium.
        try:
            browser = p.chromium.launch(channel="chrome", headless=False)
        except Exception:
            browser = p.chromium.launch(headless=False)

        context = browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
        )
        page = context.new_page()

        # Try to navigate automatically; if it fails the user can paste the
        # URL manually into the address bar — the wait_for_url below will
        # still detect when they land on classes.ku.edu.
        try:
            page.goto(LOGIN_URL, wait_until="domcontentloaded", timeout=20_000)
        except Exception:
            print("Auto-navigation failed — paste the URL above into the")
            print("address bar and complete the login manually.\n")

        # Hand control to the user — no URL detection needed.
        # Once they can see instructor names on the page, they press Enter.
        try:
            input("Finish logging in, then press Enter here to save and close... ")
        except EOFError:
            pass  # non-interactive shell

        context.storage_state(path=str(state_path))
        browser.close()

    print(f"\nSession saved to {state_path}")


def _session_looks_expired(html: str) -> bool:
    """Heuristic: if the response HTML contains a CAS/SSO login form, the session expired."""
    lower = html.lower()
    return "cas" in lower and ("login" in lower or "username" in lower)


# ---------------------------------------------------------------------------
# Scraping
# ---------------------------------------------------------------------------

def _fetch_html(form_data: dict[str, str], state_path: Path | None) -> str:
    """POST the search form and return the response HTML.

    The search endpoint is publicly accessible — no auth required.
    If state_path is given (saved login state), instructor names and class
    locations will be populated; without it those fields are hidden by the site.
    """
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)

        ctx_kwargs: dict = {
            "user_agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/133.0.0.0 Safari/537.36"
            ),
        }
        if state_path:
            ctx_kwargs["storage_state"] = str(state_path)

        context = browser.new_context(**ctx_kwargs)

        print("Submitting search form…")
        response = context.request.post(
            SEARCH_URL,
            form=form_data,
            timeout=0,  # no timeout — full catalog can take 7+ minutes
            headers={
                "User-Agent": (
                    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/133.0.0.0 Safari/537.36"
                ),
                "X-Requested-With": "XMLHttpRequest",
                "Content-Type": "application/x-www-form-urlencoded",
            },
        )

        status = response.status
        html = response.text()
        browser.close()

    if status != 200:
        raise RuntimeError(f"Search POST returned HTTP {status}")

    return html


def _parse_html(html: str) -> list[dict]:
    """
    Parse the course search results HTML into a list of course dicts.

    The site renders results as a table with a repeating 5-row pattern:
        row 1 (i%5==1): course header (code, name, credits, semester, honors)
        row 2 (i%5==2): description, prerequisites, corequisites, satisfies
        row 3 (i%5==3): section table (LEC/LAB/DIS/LBN rows + Notes rows)
        row 4 (i%5==4): ignored spacer
        row 5 (i%5==0): end of course — append to results
    """
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
                # ── Course header ─────────────────────────────────────────
                if row.h3:
                    raw_code = row.h3.get_text(strip=True)
                    parts = raw_code.split(" ", 1)
                    course["id"] = raw_code
                    course["subject"] = parts[0] if parts else ""
                    course["number"] = parts[1] if len(parts) > 1 else ""

                other = row.td.contents[2].get_text(strip=True).split("\n")
                course["title"] = other[0].strip()
                credits_raw = other[3].strip() if len(other) > 3 else ""
                course["credits"] = (
                    int(credits_raw) if credits_raw.isdigit() else credits_raw
                )

                if len(other) == 9:
                    course["semesterId"] = other[8].strip()
                    course["honors"] = False
                elif len(other) == 11:
                    course["semesterId"] = other[10].strip()
                    course["honors"] = True
                elif len(other) == 7:
                    course["semesterId"] = ""
                    course["honors"] = False
                else:
                    print(f"Unexpected header length {len(other)}: {other}")

            elif i % 5 == 2:
                # ── Description / prerequisites ───────────────────────────
                text = row.td.get_text(strip=True)

                description = text
                if "Prerequisite:" in text:
                    description = text.split("Prerequisite:")[0].strip()
                if "Satisfies:" in text:
                    description = description.split("Satisfies:")[0].strip()
                course["description"] = description

                prerequisite = "N/A"
                corequisite = "N/A"
                satisfies = "N/A"

                if "Prerequisite:" in text:
                    prerequisite = text.split("Prerequisite:")[1].split("\n")[0].strip()
                    if "Satisfies:" in prerequisite:
                        prerequisite = prerequisite.split("Satisfies:")[0].rstrip(". ").strip()
                    if "Corequisite" in prerequisite:
                        try:
                            prerequisite = prerequisite.split("Corequisite")[1].strip()
                        except Exception as exc:
                            print(f"Prereq parse error: {exc}")
                course["prerequisite"] = prerequisite

                if "Corequisite:" in text:
                    corequisite = text.split("Corequisite:")[1].split("\n")[0].strip()
                course["corequisite"] = corequisite

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
                # ── Section table ─────────────────────────────────────────
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
                        # Section header row: type, instructor, topic, CRN, seats
                        section_type = col0

                        instructor_tag = cols[1].find("a")
                        instructor = (
                            instructor_tag.get_text(strip=True)
                            if instructor_tag
                            else "N/A"
                        )

                        topic_parts = cols[1].contents[2].get_text(strip=True).split(":")
                        topic = topic_parts[1].strip() if len(topic_parts) > 1 else "N/A"

                        course_attribute = "N/A"
                        attr_contents = cols[2].contents
                        if len(attr_contents) > 1:
                            img = attr_contents[1]
                            src = img.get("src", "") if hasattr(img, "get") else ""
                            course_attribute = (
                                "No Cost Course Materials"
                                if src == "/Classes/img/book-icon-0.svg"
                                else "Low Cost Course Materials"
                            )

                        crn_tag = cols[3].find("strong") if len(cols) > 3 else None
                        if not crn_tag:
                            current_section = {}
                            current_id = ""
                            continue
                        current_id = crn_tag.get_text(strip=True)
                        seat_available = cols[4].get_text(strip=True) if len(cols) > 4 else "Unopened"

                        current_section = {
                            "id": current_id,
                            "type": section_type,
                            "instructor": instructor,
                            "topic": topic,
                            "courseAttribute": course_attribute,
                            "seatAvailable": seat_available,
                        }

                    elif col0 and col0 not in ("Notes", "Dept Req", "") and "Notes" not in col0:
                        print(f"  [unknown type] course={course.get('id','')} col0={col0!r}")

                    elif "Notes" in col0 and current_id:
                        # Notes row: meeting time + location
                        location = "OFF CMPS-K"
                        loc_tag = cols[1].span

                        if loc_tag:
                            if loc_tag.find("img") or loc_tag.get_text() == "":
                                pass  # no location info
                            else:
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

                        if "meetingTime" in current_section and "location" in current_section:
                            section_list.append(current_section.copy())
                            current_section = {}
                            current_id = ""

                course["components"] = section_list

            elif i % 5 == 0:
                # ── End of course ─────────────────────────────────────────
                if course.get("satisfies") and course["satisfies"] != "N/A":
                    course["satisfied"] = [
                        s.strip() for s in course["satisfies"].split(" & ")
                    ]
                course_list.append(course.copy())
                course.clear()

        except Exception as exc:
            print(f"Parse error at row {i}: {exc}")

        i += 1

    return course_list


def scrape_courses(
    form_data: dict[str, str] | None = None,
    limit: int | None = None,
) -> list[dict]:
    """
    Main entry point.  Returns a list of course dicts.

    Auth is optional — the search works without it, but instructor names and
    class locations will be absent.  Run with --login first to include them.

    Args:
        form_data: overrides for DEFAULT_FORM fields.
        limit: if given, truncate results to this many courses (useful for testing).
    """
    state_path = AUTH_STATE_PATH if AUTH_STATE_PATH.exists() else None
    if not state_path:
        print(
            "Note: no saved session found — instructor names and locations will be N/A.\n"
            f"      Run with --login to include them (saves to {AUTH_STATE_PATH})."
        )

    data = {**DEFAULT_FORM, **(form_data or {})}
    html = _fetch_html(data, state_path)
    courses = _parse_html(html)
    return courses[:limit] if limit else courses


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scrape KU course catalog and write to JSON.",
    )
    parser.add_argument(
        "--login",
        action="store_true",
        help="Open a visible browser to log in via KU SSO and save the session.",
    )
    parser.add_argument(
        "--term",
        default=DEFAULT_FORM["searchTerm"],
        help="KU term code (default: %(default)s = Spring 2025).",
    )
    parser.add_argument(
        "--out",
        default=str(Path(__file__).parent.parent / "courseDatabase.json"),
        help="Output JSON file path (default: %(default)s).",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Truncate output to N courses (useful for quick testing).",
    )
    parser.add_argument(
        "--search",
        default="",
        help="Filter courses by text (e.g. 'EECS 388'). Narrows server response, speeds up testing.",
    )
    parser.add_argument(
        "--career",
        default=DEFAULT_FORM["searchCareer"],
        choices=["Undergraduate", "Graduate", "UndergraduateGraduate"],
        help="Career level to scrape (default: %(default)s).",
    )
    parser.add_argument(
        "--append",
        action="store_true",
        help="Add this term to the existing database instead of overwriting it.",
    )
    parser.add_argument(
        "--check-auth",
        action="store_true",
        help="Test whether the saved browser session is still valid (has instructor data).",
    )
    parser.add_argument(
        "--update",
        action="store_true",
        help=(
            "Upsert scraped courses into the existing database: update matching "
            "courses in place (refreshing instructor/location/seats) and append "
            "any new ones. Courses not in the scrape are left untouched."
        ),
    )
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()

    if args.login:
        login_and_save_state(AUTH_STATE_PATH)
        print("Login complete. You can now run without --login.")
        sys.exit(0)

    if args.check_auth:
        if not AUTH_STATE_PATH.exists():
            print("No saved session found. Run with --login first.")
            sys.exit(1)
        print("Testing session with a quick search...")
        test_data = {**DEFAULT_FORM, "searchTerm": args.term, "classesSearchText": "EECS 388"}
        html = _fetch_html(test_data, AUTH_STATE_PATH)
        if _session_looks_expired(html):
            print("Session EXPIRED. Re-run with --login to refresh.")
            sys.exit(1)
        courses = _parse_html(html)
        if not courses:
            print("Got no results — check the term code or try a different query.")
            sys.exit(1)
        # Check if any section has a real instructor name (not N/A)
        has_instructor = any(
            comp.get("instructor") not in (None, "N/A", "")
            for c in courses
            for comp in c.get("components", [])
        )
        if has_instructor:
            print("Session is VALID. Instructor names are present.")
            sys.exit(0)
        else:
            print("Session EXPIRED or limited — instructor names are missing.")
            sys.exit(1)

    print(f"Scraping term {args.term}…")
    try:
        form_overrides: dict[str, str] = {"searchTerm": args.term, "searchCareer": args.career}
        if args.search:
            form_overrides["classesSearchText"] = args.search
        courses = scrape_courses(form_overrides, limit=args.limit)
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    # Load existing semesters if --append or --update, otherwise start fresh.
    semesters_data: dict[str, list] = {}
    if (args.append or args.update) and out_path.exists():
        with open(out_path, encoding="utf-8") as f:
            existing = json.load(f)
        if isinstance(existing, dict) and "semesters" in existing:
            semesters_data = existing["semesters"]
        elif isinstance(existing, dict) and "term" in existing:
            # Migrate single-term format.
            semesters_data = {existing["term"]: existing.get("courses", [])}

    if args.update:
        # Upsert: update existing courses in place, append new ones.
        existing_term = semesters_data.get(args.term, [])
        by_id: dict[str, dict] = {c["id"]: c for c in existing_term}
        updated = added = 0
        for course in courses:
            cid = course.get("id")
            if cid in by_id:
                by_id[cid] = course
                updated += 1
            else:
                by_id[cid] = course
                added += 1
        semesters_data[args.term] = list(by_id.values())
        print(f"Updated {updated} existing and added {added} new courses for term {args.term}")
    else:
        semesters_data[args.term] = courses

    with open(out_path, "w", encoding="utf-8") as f:
        json.dump({"semesters": semesters_data}, f, indent=2, ensure_ascii=False)

    n_terms = len(semesters_data)
    print(f"Wrote {len(semesters_data[args.term])} courses for term {args.term} to {out_path} ({n_terms} term(s) total)")
