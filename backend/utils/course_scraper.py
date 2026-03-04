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

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeout

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

SEARCH_URL = "https://classes.ku.edu/Classes/CourseSearch.action"

# Where the saved browser state lives.  Not committed to git.
AUTH_STATE_PATH = Path(__file__).parent.parent / "auth" / "browser_state.json"

DEFAULT_FORM = {
    "classesSearchText": "",
    "searchCareer": "Undergraduate",
    "searchTerm": "4252",          # Spring 2025 — change per term
    "searchCourseNumberMin": "001",
    "searchCourseNumberMax": "999",
    "searchClosed": "false",
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
    print(f"  --> Paste this URL into the browser that opens:")
    print(f"      {SEARCH_URL}")
    print()
    print("Log in through KU SSO. The script saves state automatically")
    print("once you land back on classes.ku.edu (you have 5 minutes).\n")

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
            page.goto(SEARCH_URL, wait_until="domcontentloaded", timeout=20_000)
        except Exception:
            print("Auto-navigation failed — paste the URL above into the")
            print("address bar and complete the login manually.\n")

        # Poll page.url every second until we land on classes.ku.edu.
        # wait_for_url() breaks on KU's multi-step SSO redirect chain because
        # the frame gets detached mid-redirect; polling avoids that entirely.
        print("Waiting for you to complete login…")
        deadline = time.time() + 300  # 5 minutes
        landed = False
        while time.time() < deadline:
            try:
                current = page.url
                if (
                    "classes.ku.edu" in current
                    and "login" not in current
                    and "cas" not in current.lower()
                ):
                    landed = True
                    break
            except Exception:
                pass  # page may be mid-navigation
            time.sleep(1)

        if not landed:
            print("Timed out (5 min). Please re-run --login and try again.",
                  file=sys.stderr)
            browser.close()
            sys.exit(1)

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

def _fetch_html(form_data: dict[str, str], state_path: Path) -> str:
    """POST the search form using saved session state and return the response HTML."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(storage_state=str(state_path))

        response = context.request.post(
            SEARCH_URL,
            form=form_data,
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

        html = response.text()
        browser.close()

    if response.status != 200:
        raise RuntimeError(f"Search POST returned HTTP {response.status}")

    if _session_looks_expired(html):
        raise RuntimeError(
            "Session appears to have expired. Re-run with --login to refresh."
        )

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

                    if col0 in ("LEC", "LBN", "DIS", "LAB"):
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

                        current_id = cols[3].find("strong").get_text(strip=True)
                        seat_available = cols[4].get_text(strip=True)

                        current_section = {
                            "id": current_id,
                            "type": section_type,
                            "instructor": instructor,
                            "topic": topic,
                            "courseAttribute": course_attribute,
                            "seatAvailable": seat_available,
                        }

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


def scrape_courses(form_data: dict[str, str] | None = None) -> list[dict]:
    """
    Main entry point.  Returns a list of course dicts.

    Raises RuntimeError if the saved session is missing or expired.
    Call login_and_save_state() first, or run with --login.
    """
    if not AUTH_STATE_PATH.exists():
        raise RuntimeError(
            f"No saved session found at {AUTH_STATE_PATH}. "
            "Run with --login to authenticate first."
        )

    data = {**DEFAULT_FORM, **(form_data or {})}
    html = _fetch_html(data, AUTH_STATE_PATH)
    return _parse_html(html)


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
    return parser


if __name__ == "__main__":
    args = _build_parser().parse_args()

    if args.login:
        login_and_save_state(AUTH_STATE_PATH)
        print("Login complete. You can now run without --login.")
        sys.exit(0)

    print(f"Scraping term {args.term}…")
    try:
        courses = scrape_courses({"searchTerm": args.term})
    except RuntimeError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(courses, f, indent=2, ensure_ascii=False)

    print(f"Wrote {len(courses)} courses to {out_path}")
