def check_conflicts(selected_courses, database):
    schedule = {}

    for course_code in selected_courses:
        course = database.get(course_code, {})
        sections = course.get("Sections", {})

        for sec_id, sec_info in sections.items():
            time_slot = sec_info.get("MeetingTime", "")

            if time_slot in schedule:
                return f"Time conflict detected between {schedule[time_slot]} and {course_code}"
            
            schedule[time_slot] = course_code
    
    return None
