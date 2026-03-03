import pytest
from src.catalog.meeting_parser import parse_meeting_time


# ---------------------------------------------------------------------------
# None / empty / N/A inputs
# ---------------------------------------------------------------------------

def test_none_returns_empty():
    assert parse_meeting_time(None) == []

def test_empty_string_returns_empty():
    assert parse_meeting_time("") == []

def test_na_returns_empty():
    assert parse_meeting_time("N/A") == []

def test_tba_returns_empty():
    assert parse_meeting_time("TBA") == []

def test_whitespace_only_returns_empty():
    assert parse_meeting_time("   ") == []


# ---------------------------------------------------------------------------
# AM patterns
# ---------------------------------------------------------------------------

def test_mwf_am():
    result = parse_meeting_time("MWF 08:00 - 08:50 AM")
    assert result == [{"days": ["M", "W", "F"], "startTime": "08:00", "endTime": "08:50"}]

def test_tuth_am():
    result = parse_meeting_time("TuTh 09:30 - 10:45 AM")
    assert result == [{"days": ["T", "Th"], "startTime": "09:30", "endTime": "10:45"}]

def test_single_m_am():
    result = parse_meeting_time("M 09:00 - 09:50 AM")
    assert result == [{"days": ["M"], "startTime": "09:00", "endTime": "09:50"}]

def test_th_am():
    result = parse_meeting_time("Th 08:00 - 08:50 AM")
    assert result == [{"days": ["Th"], "startTime": "08:00", "endTime": "08:50"}]

def test_tu_am():
    result = parse_meeting_time("Tu 09:30 - 10:45 AM")
    assert result == [{"days": ["T"], "startTime": "09:30", "endTime": "10:45"}]

def test_sa_am():
    result = parse_meeting_time("Sa 09:30 - 12:50 PM")
    assert result == [{"days": ["Sa"], "startTime": "09:30", "endTime": "12:50"}]

def test_mw_am():
    result = parse_meeting_time("MW 11:00 - 12:15 PM")
    assert result == [{"days": ["M", "W"], "startTime": "11:00", "endTime": "12:15"}]


# ---------------------------------------------------------------------------
# PM patterns — 12h→24h conversion
# ---------------------------------------------------------------------------

def test_tuth_pm():
    result = parse_meeting_time("TuTh 02:30 - 03:45 PM")
    assert result == [{"days": ["T", "Th"], "startTime": "14:30", "endTime": "15:45"}]

def test_m_evening():
    result = parse_meeting_time("M 06:00 - 09:00 PM")
    assert result == [{"days": ["M"], "startTime": "18:00", "endTime": "21:00"}]

def test_w_afternoon():
    result = parse_meeting_time("W 04:30 - 07:00 PM")
    assert result == [{"days": ["W"], "startTime": "16:30", "endTime": "19:00"}]

def test_mwf_pm():
    result = parse_meeting_time("MWF 01:00 - 01:50 PM")
    assert result == [{"days": ["M", "W", "F"], "startTime": "13:00", "endTime": "13:50"}]


# ---------------------------------------------------------------------------
# AM start, PM end (cross-meridiem — e.g. 11:00 AM - 12:15 PM)
# ---------------------------------------------------------------------------

def test_mw_cross_meridiem():
    # Start 11 AM, end 12:15 PM — both stated as PM but start_h > end_h
    result = parse_meeting_time("MW 11:00 - 12:15 PM")
    assert result == [{"days": ["M", "W"], "startTime": "11:00", "endTime": "12:15"}]

def test_tuth_cross_meridiem():
    result = parse_meeting_time("TuTh 11:00 - 12:15 PM")
    assert result == [{"days": ["T", "Th"], "startTime": "11:00", "endTime": "12:15"}]


# ---------------------------------------------------------------------------
# Noon edge cases (12:xx PM = 12:xx, 12:xx AM = 00:xx)
# ---------------------------------------------------------------------------

def test_noon_pm():
    result = parse_meeting_time("M 12:00 - 12:50 PM")
    assert result == [{"days": ["M"], "startTime": "12:00", "endTime": "12:50"}]

def test_midnight_am():
    result = parse_meeting_time("M 12:00 - 12:50 AM")
    assert result == [{"days": ["M"], "startTime": "00:00", "endTime": "00:50"}]


# ---------------------------------------------------------------------------
# Complex day combos observed in real data
# ---------------------------------------------------------------------------

def test_mtuwthf():
    result = parse_meeting_time("MTuWThF 09:00 - 09:50 AM")
    assert result == [{"days": ["M", "T", "W", "Th", "F"], "startTime": "09:00", "endTime": "09:50"}]

def test_mtuwth():
    result = parse_meeting_time("MTuWTh 10:00 - 10:50 AM")
    assert result == [{"days": ["M", "T", "W", "Th"], "startTime": "10:00", "endTime": "10:50"}]

def test_mtu():
    result = parse_meeting_time("MTu 01:00 - 02:15 PM")
    assert result == [{"days": ["M", "T"], "startTime": "13:00", "endTime": "14:15"}]

def test_mth():
    result = parse_meeting_time("MTh 08:00 - 09:15 AM")
    assert result == [{"days": ["M", "Th"], "startTime": "08:00", "endTime": "09:15"}]

def test_wf():
    result = parse_meeting_time("WF 09:00 - 09:50 AM")
    assert result == [{"days": ["W", "F"], "startTime": "09:00", "endTime": "09:50"}]

def test_tuf():
    result = parse_meeting_time("TuF 10:00 - 10:50 AM")
    assert result == [{"days": ["T", "F"], "startTime": "10:00", "endTime": "10:50"}]

def test_mf():
    result = parse_meeting_time("MF 01:00 - 01:50 PM")
    assert result == [{"days": ["M", "F"], "startTime": "13:00", "endTime": "13:50"}]


# ---------------------------------------------------------------------------
# Robustness: extra whitespace
# ---------------------------------------------------------------------------

def test_extra_whitespace():
    result = parse_meeting_time("  TuTh  09:30 - 10:45 AM  ")
    assert result == [{"days": ["T", "Th"], "startTime": "09:30", "endTime": "10:45"}]
