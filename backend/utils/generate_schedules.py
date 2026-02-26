from itertools import product

def generate_possible_schedules(selected_courses, database):
    all_section_combinations = []

    for course_code in selected_courses:
        course = database.get(course_code, {})
        sections = course.get("Sections", {}).values()
        all_section_combinations.append(list(sections))
    
    valid_schedules = []
    for combination in product(*all_section_combinations):
        time_slots = {}
        conflict = False

        for section in combination:
            time = section["MeetingTime"]
            if time in time_slots:
                conflict = True
                break
            time_slots[time] = section

        if not conflict:
            valid_schedules.append(combination)
    
    return valid_schedules
