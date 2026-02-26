from flask import Flask, request, jsonify
from flask_cors import CORS
import json
import os
from utils.schedule_checker import check_conflicts
from utils.generate_schedules import generate_possible_schedules
from utils.course_scraper import scrape_course

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend requests

# Load course database
COURSE_DB_FILE = "courseDatabase.json"

def load_courses():
    if os.path.exists(COURSE_DB_FILE):
        with open(COURSE_DB_FILE, "r") as f:
            data = json.load(f)
            if isinstance(data, dict):  # 🔹 Convert to list if needed
                return list(data.values())
            return data
    return []

database = load_courses()


@app.route("/search", methods=["GET"])
def search_courses():
    query = request.args.get("query", "").strip().lower()
    level = request.args.get("level", "undergrad").lower()
    semester = request.args.get("semester", "Spring 2025").strip()

    results = []
    for course_code, details in database.items():
        if semester != details.get("CourseSemester", "None"):  # Ensure correct semester
            continue
        if query in course_code.lower() or query in details.get("CourseName", "").lower():
            results.append({
                "courseCode": course_code,
                "courseName": details.get("CourseName", ""),
                "creditHours": details.get("CreditHours", ""),
                "prerequisite": details.get("Prerequisite", "N/A"),
                "corequisite": details.get("Corequisite", "N/A"),
                "satisfies": details.get("Satisfies", "N/A"),
                "sections": details.get("Sections", {}),
            })
        if len(results) >= 3:  # Limit to 3 suggestions
            break

    return jsonify(results)


@app.route("/get_course", methods=["GET"])
def get_course():
    course_code = request.args.get("courseCode", "").strip()
    print(f"📌 [STEP 1] Received course request for: {course_code}")  # ✅ Check incoming request

    # Ensure database is a list
    if not isinstance(database, list):
        print("❌ [ERROR] Database is not a list!")
        return jsonify({"error": "Database format incorrect"}), 500

    for course in database:
        print(f"🔎 [STEP 2] Checking course: {course}")  # ✅ Print each course before checking
        if isinstance(course, dict) and course.get("CourseCode") == course_code:
            print(f"✅ [STEP 3] Found course: {course}")  # ✅ Confirm match
            return jsonify(course)

    print("❌ [ERROR] Course not found")
    return jsonify({"error": "Course not found"}), 404

@app.route("/generate_schedule_combinations", methods=["POST"])
def generate_schedule_combinations():
    selected_courses = request.json.get("courses", [])
    all_combinations = []

    # Extract all sections for selected courses
    course_sections = []
    for course_code in selected_courses:
        course = database.get(course_code, {})
        sections = list(course.get("Sections", {}).values())
        if sections:
            course_sections.append(sections)

    # Generate all possible schedules
    for combination in permutations(course_sections, len(course_sections)):
        schedule = []
        time_slots = set()
        has_conflict = False

        for section in combination:
            meeting_time = section.get("MeetingTime", "")
            if meeting_time in time_slots:  # Check for conflicts
                has_conflict = True
                break
            time_slots.add(meeting_time)
            schedule.append(section)

        if not has_conflict:
            all_combinations.append(schedule)

    return jsonify({"schedules": all_combinations})

@app.route("/check_conflict", methods=["POST"])
def check_conflict():
    selected_courses = request.json.get("courses", [])
    schedule = {}

    for course_code in selected_courses:
        course = database.get(course_code, {})
        sections = course.get("Sections", {})

        for sec_id, sec_info in sections.items():
            time_slot = sec_info.get("MeetingTime", "")
            if time_slot in schedule:
                return jsonify({"error": f"Time conflict detected between {schedule[time_slot]} and {course_code}"})
            schedule[time_slot] = course_code

    return jsonify({"message": "No conflicts detected"})

if __name__ == "__main__":
    app.run(debug=True)