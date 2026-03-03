from __future__ import annotations

_SEASON_CODE: dict[str, str] = {
    "2": "SP",  # Spring
    "6": "SU",  # Summer
    "9": "FA",  # Fall
}


def term_code_to_semester_id(term_code: str | int) -> str:
    """
    Decode a KU term code into a semester ID string.

    KU term code format: "4" + YY + S
      - "4"  : fixed university prefix
      - YY   : last two digits of the calendar year
      - S    : season digit  (2=Spring, 6=Summer, 9=Fall)

    Examples:
        "4252" -> "2025SP"   (Spring 2025)
        "4259" -> "2025FA"   (Fall 2025)
        "4256" -> "2025SU"   (Summer 2025)
        "4262" -> "2026SP"   (Spring 2026)
    """
    s = str(term_code).strip()
    if len(s) != 4 or not s.isdigit() or s[0] != "4":
        raise ValueError(f"Unrecognised KU term code: {term_code!r}")
    yy = s[1:3]
    season_digit = s[3]
    season = _SEASON_CODE.get(season_digit)
    if season is None:
        raise ValueError(f"Unknown season digit {season_digit!r} in term code {term_code!r}")
    return f"20{yy}{season}"


def term_code_to_label(term_code: str | int) -> str:
    """
    Return a human-readable semester label for a KU term code.

    Examples:
        "4252" -> "Spring 2025"
        "4259" -> "Fall 2025"
        "4256" -> "Summer 2025"
    """
    s = str(term_code).strip()
    if len(s) != 4 or not s.isdigit() or s[0] != "4":
        raise ValueError(f"Unrecognised KU term code: {term_code!r}")
    yy = s[1:3]
    season_digit = s[3]
    season_labels = {"2": "Spring", "6": "Summer", "9": "Fall"}
    season = season_labels.get(season_digit)
    if season is None:
        raise ValueError(f"Unknown season digit {season_digit!r} in term code {term_code!r}")
    return f"{season} 20{yy}"
