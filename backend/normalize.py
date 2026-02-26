import re  
import json

def normalize_course_code(code: str) -> str:
    return re.sub(r"\s+", " ", code.strip())

def split_course_code(code: str):
    norm = normalize_course_code(code)
    m = re.match(r"^([A-Za-z&]+)\s+(\d+[A-Za-z]?)$", norm)
    if m:
        return m.group(1), m.group(2)
    parts = norm.split(" ")
    subject = parts[0] if parts else norm
    number = " ".join(parts[1:]) if len(parts) > 1 else ""
    return subject, number

def parse_satisfied(raw: str | None):
    if not raw or raw.strip() == "N/A":
        return None
    return [x.strip() for x in raw.split("&") if x.strip()]

def to_component_type(t: str | None):
    v = (t or "LEC").upper()
    return v if v in {"LEC", "LAB", "DIS", "REC"} else "LEC"

def transform_course(old: dict, semester_id: str) -> dict:
    subject, number = split_course_code(old.get("CourseCode", ""))
    course_id = f"{subject} {number}".strip()

    sections = old.get("Sections", {}) or {}
    components = []
    for section_id, s in sections.items():
        components.append({
            "id": str(section_id),
            "type": to_component_type(s.get("SectionType")),
            "meetingTime": None if s.get("MeetingTime") in (None, "N/A") else s.get("MeetingTime"),
            "instructor": None if s.get("Instructor") in (None, "N/A") else s.get("Instructor"),
            "location": None if s.get("Location") in (None, "N/A") else s.get("Location"),
        })

    credits_raw = old.get("CreditHours")
    credits = int(credits_raw) if credits_raw and credits_raw.isdigit() else None
    
    prereq = old.get("Prerequisite")
    prereq_main = re.split(r"\bSatisfies\b\s*:?", prereq, flags=re.IGNORECASE)[0]
    prereq_main = prereq_main.replace(".Satisfies", ".").strip()

    description = old.get("CourseDescription")
    description_main = re.split(r"\bPrerequisite\b\s*:?", description, flags=re.IGNORECASE)[0]
    description_main = description_main.replace("Prerequisite", "").strip()
    out = {
        "id": course_id,
        "subject": subject,
        "number": number,
        "title": old.get("CourseName"),
        "description": description_main,
        "prerequisite": prereq_main,
        "corequisite": old.get("Corequisite"),
        "satisfies": old.get("Satisfies"),
        "semesterId": semester_id,
        "components": components,
    }
    if credits is not None:
        out["credits"] = credits

    satisfied = parse_satisfied(old.get("Satisfies"))
    if satisfied:
        out["satisfied"] = satisfied
    return out


if __name__ == "__main__":
    with open("courseDatabase.json", "r") as f:
        data = json.load(f)

    new_data = [transform_course(course, "") for course in data]
    with open("normalized_courseDatabase.json", "w") as f:
        json.dump(new_data, f, indent=4)