from __future__ import annotations
import re
from typing import TypedDict


class ParsedMeeting(TypedDict):
    days: list[str]
    startTime: str
    endTime: str


# Greedy day token map — try 2-char tokens before 1-char to avoid
# misreading "Th" as "T" + "h" or "Tu" as "T" + "u".
_TWO_CHAR: dict[str, str] = {
    "Tu": "T",
    "Th": "Th",
    "Sa": "Sa",
    "Su": "Su",
}
_ONE_CHAR: dict[str, str] = {
    "M": "M",
    "W": "W",
    "F": "F",
}

_MEETING_RE = re.compile(
    r"^(?P<days>[A-Za-z]+)\s+"
    r"(?P<sh>\d{1,2}):(?P<sm>\d{2})\s*-\s*"
    r"(?P<eh>\d{1,2}):(?P<em>\d{2})\s*"
    r"(?P<meridiem>AM|PM)$"
)


def _parse_days(raw: str) -> list[str]:
    """
    Greedily split a concatenated day string into frontend DayOfWeek tokens.

    Examples:
        "TuTh"     -> ["T", "Th"]
        "MWF"      -> ["M", "W", "F"]
        "MTuWThF"  -> ["M", "T", "W", "Th", "F"]
        "Sa"       -> ["Sa"]
    """
    result: list[str] = []
    i = 0
    while i < len(raw):
        two = raw[i : i + 2]
        if two in _TWO_CHAR:
            result.append(_TWO_CHAR[two])
            i += 2
        elif raw[i] in _ONE_CHAR:
            result.append(_ONE_CHAR[raw[i]])
            i += 1
        else:
            # Skip unrecognised characters rather than crash.
            i += 1
    return result


def _to_24h(hour: int, minute: int, meridiem: str) -> str:
    """Convert 12-hour clock values to a zero-padded 24-hour "HH:MM" string."""
    if meridiem == "AM":
        h = 0 if hour == 12 else hour
    else:  # PM
        h = hour if hour == 12 else hour + 12
    return f"{h:02d}:{minute:02d}"


def _to_minutes(hour: int, minute: int, meridiem: str) -> int:
    """Return minutes-since-midnight for a 12h time."""
    h24 = int(_to_24h(hour, minute, meridiem).split(":")[0])
    return h24 * 60 + minute


def parse_meeting_time(raw: str | None) -> list[ParsedMeeting]:
    """
    Parse a KU raw MeetingTime string into a list of Meeting dicts.

    Returns an empty list for None, "N/A", or any unparseable string
    (treated as TBA / online).

    Examples:
        "TuTh 09:30 - 10:45 AM" -> [{"days": ["T", "Th"],
                                       "startTime": "09:30",
                                       "endTime": "10:45"}]
        "MWF 08:00 - 08:50 AM"  -> [{"days": ["M", "W", "F"],
                                       "startTime": "08:00",
                                       "endTime": "08:50"}]
        "M 06:00 - 09:00 PM"    -> [{"days": ["M"],
                                       "startTime": "18:00",
                                       "endTime": "21:00"}]
        "N/A"                   -> []
        None                    -> []
    """
    if not raw:
        return []
    cleaned = raw.strip()
    if not cleaned or cleaned.upper() in {"N/A", "NA", "TBA", "NONE"}:
        return []

    m = _MEETING_RE.match(cleaned)
    if not m:
        return []

    days = _parse_days(m.group("days"))
    if not days:
        return []

    meridiem = m.group("meridiem")
    start_h, start_m = int(m.group("sh")), int(m.group("sm"))
    end_h, end_m = int(m.group("eh")), int(m.group("em"))

    # The suffix applies to the END time. Infer start meridiem by trying the
    # same suffix first; if that would make start >= end (impossible for a
    # same-day class), flip to the other meridiem.
    end_minutes = _to_minutes(end_h, end_m, meridiem)
    other = "AM" if meridiem == "PM" else "PM"
    start_minutes_same = _to_minutes(start_h, start_m, meridiem)
    start_meridiem = meridiem if start_minutes_same < end_minutes else other

    return [
        ParsedMeeting(
            days=days,
            startTime=_to_24h(start_h, start_m, start_meridiem),
            endTime=_to_24h(end_h, end_m, meridiem),
        )
    ]
