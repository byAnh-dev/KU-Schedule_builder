"""
In-memory seat availability store.

Loaded from seats.json at startup and refreshed every 5 minutes by a
background thread.  seats.json is written externally by
backend/utils/refresh_seats.py (run via cron).
"""
from __future__ import annotations

import json
import os
import threading
import time
from typing import Any

_BACKEND_DIR = os.path.dirname(os.path.dirname(os.path.dirname(__file__)))
_SEATS_PATH = os.path.join(_BACKEND_DIR, "seats.json")

_seats: dict[str, Any] = {}
_lock = threading.Lock()


def load_seats() -> None:
    """Load seats.json into memory. Safe to call multiple times."""
    global _seats
    if not os.path.exists(_SEATS_PATH):
        return
    try:
        with open(_SEATS_PATH, encoding="utf-8") as f:
            data = json.load(f)
        with _lock:
            _seats = {k: v for k, v in data.items() if not k.startswith("_")}
        print(f"[seats] Loaded {len(_seats)} CRN records")
    except Exception as exc:
        print(f"[seats] Failed to load seats.json: {exc}")


def get_seat(crn: str) -> int | str | None:
    with _lock:
        return _seats.get(crn)


def apply_to_course(course: dict[str, Any]) -> dict[str, Any]:
    """Return a copy of course with seatAvailable patched from the seats store."""
    updated = []
    changed = False
    for comp in course.get("components", []):
        crn = comp.get("crn")
        if crn:
            fresh = get_seat(crn)
            if fresh is not None:
                comp = {**comp, "seatAvailable": fresh}
                changed = True
        updated.append(comp)
    if not changed:
        return course
    return {**course, "components": updated}


def start_background_reload(interval_seconds: int = 300) -> None:
    """Daemon thread that reloads seats.json every `interval_seconds` (default 5 min)."""
    def _loop() -> None:
        while True:
            time.sleep(interval_seconds)
            try:
                load_seats()
            except Exception as exc:
                print(f"[seats] Background reload error (will retry in {interval_seconds}s): {exc}")

    t = threading.Thread(target=_loop, daemon=True, name="seats-reloader")
    t.start()
