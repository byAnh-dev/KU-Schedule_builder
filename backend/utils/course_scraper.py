import requests
from bs4 import BeautifulSoup


URL = "https://classes.ku.edu/Classes/CourseSearch.action"
header = {
    "User-Agent":"Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/133.0.0.0 Safari/537.36",
    "X-Requested-With": "XMLHttpRequest",
     "Content-Type": "application/x-www-form-urlencoded"
}
def scrape_course(course_code):
    form_data = {
        "classesSearchText": "",
        "searchCareer": "Undergraduate",
        "searchTerm":"4252",
        "searchCourseNumberMin": "001",
        "searchCourseNumberMax":"999",
        "searchClosed": "false",
        "searchHonorsClasses":"false",
        "searchShortClasses":"false",
        "searchIncludeExcludeDays": "include"
    }
    response = requests.post(URL,headers= header, data=form_data)

    if response.status_code == 200:
        print("Successfully fetched!")
    else:
        print(f"Failed to fetch data: {response.status_code}")
    web_data = BeautifulSoup(response.text, "html.parser")
    tableExtract = web_data.table.find_all("tr", class_= None, id_ = None)
    i = 1
    classInfo = [] #Contains all the courses
    course = {}#Contain info of 1 course
    for classSection in tableExtract:
        classList = {}
        try:
            if i % 5 == 1: #Read the first line - Take out courseCode, courseName, creditHours
                if classSection.h3:
                    courseCode = classSection.h3.getText(strip = True)
                    course.update({"CourseCode":courseCode})
                
                courseOtherInfo = classSection.td.contents[2].get_text(strip=True).split("\n")
                
                courseName = courseOtherInfo[0].strip()
                course.update({"CourseName":courseName})
                
                creditHours =courseOtherInfo[3].strip()
                course.update({"CreditHours":creditHours})
                
                if len(courseOtherInfo) == 9:
                    courseSemester = courseOtherInfo[8].strip()
                    course.update({"CourseSemester":courseSemester})
                    course.update({"Honors":"No"})
                elif len(courseOtherInfo) == 11:
                    courseSemester = courseOtherInfo[10].strip()
                    course.update({"CourseSemester":courseSemester})
                    course.update({"Honors":"Yes"})
                elif len(courseOtherInfo) == 7:
                    course.update({"CourseSemester":"None"})
                    course.update({"Honors":"No"})
                else:
                    print(f"Abnormal course:{courseOtherInfo}")
            elif i % 5 == 2: #Read the second block - Take out courseDescription, Pre-Coreq and Satisfies
                courseDescriptionTag = classSection.td.getText(strip=True)
                if "Prerequisite:" in courseDescriptionTag:
                    courseDescription = courseDescriptionTag.split("Prerequisite:")[0].strip()
                if "Satisfies:" in courseDescriptionTag:
                    courseDescription = courseDescriptionTag.split("Satisfies:")[0].strip()
                course.update({"CourseDescription":courseDescription})
                prerequisite = "N/A"
                corequisite = "N/A"
                satisfies = "N/A"

                # Look for specific keywords in description
                if "Prerequisite:" in courseDescriptionTag:
                    prerequisite = courseDescriptionTag.split("Prerequisite:")[1].split("\n")[0].strip()
                    if "Corequisite" in prerequisite:
                        try:
                            prerequisite = prerequisite.split("Corequisite")[1].strip()
                        except Exception as e:
                            print(f"{prerequisite} with {e}")
                course.update({"Prerequisite":prerequisite})

                if "Corequisite:" in courseDescriptionTag:
                    corequisite = courseDescriptionTag.split("Corequisite:")[1].split("\n")[0].strip()
                course.update({"Corequisite":corequisite})

                if "Satisfies:" in courseDescriptionTag:
                    goalString = courseDescriptionTag.split("Satisfies:")[1].strip()
                    
                    goals = goalString.split(",")
                    cleaned_goals = []
                    for goal in goals:
                        eachgoal = goal.split("\n")
                        eachgoal = [word.strip() for word in eachgoal if word.strip()]
                        cleaned_goals.append(" ".join(eachgoal))
                    # Correct final string joining
                    satisfies = " & ".join(cleaned_goals)
                course.update({"Satisfies":satisfies})
                    
            elif i % 5 == 3:
                # Extract all rows without filtering by class
                classTable = classSection.table.find_all("tr")


                classSchedule = {}  # Stores current section data
                classNumber = ""

                for row in classTable:
                    cols = row.find_all("td")

                    # Skip rows that don't have enough columns
                    if len(cols) < 2:
                        continue

                    # Check if it's the first row (Section Information)
                    if cols[0].text.strip() in ["LEC", "LBN", "DIS", "LAB"]:  
                        sectionType = cols[0].text.strip()
                        instructorTag = cols[1].find("a")
                        instructor = instructorTag.text.strip() if instructorTag else "Unknown"

                        topicTag = cols[1].contents[2].get_text(strip=True).split(":")
                        if len(topicTag) > 1:
                            topic = topicTag[1].strip() 
                        else:
                            topic = "N/A"
                        

                        courseAttribute = "N/A"
                        courseAttributeTag = cols[2].contents
                        if len(courseAttributeTag) > 1:
                            if "src" in courseAttributeTag[1].attrs and courseAttributeTag[1]['src'] == "/Classes/img/book-icon-0.svg":
                                courseAttribute = "No Cost Course Materials"
                            else:
                                courseAttribute = "Low Cost Course Materials"

                        classNumber = cols[3].find("strong").text.strip()
                        seatsAvailable = cols[4].text.strip()

                        # Store section details
                        classSchedule = {
                            "SectionType": sectionType,
                            "Instructor": instructor,
                            "Topic": topic,
                            "CourseAttribute": courseAttribute,
                            "SeatAvailable": seatsAvailable
                        }

                    # Check if it's the second row (Time & Location)
                    elif "Notes" in cols[0].text.strip():
                        
                        Location = "OFF CMPS-K"
                        locationTag = cols[1].span
            
                        if locationTag:
                            if locationTag.find("img") or locationTag.get_text() == '':
                                continue
                            else:
                                locationText = locationTag.string.strip()
                                if locationText == "ONLNE CRSE":
                                    Location = "Online"
                                elif locationText == "KULC APPT":
                                    Location = "By Appointment"
                                else:
                                    campus = ''
                                    if len(cols[1].contents) == 11:
                                        campus = cols[1].contents[6].get_text(strip=True)
                                    elif len(cols[1].contents) == 15:
                                        campus = cols[1].contents[12].get_text(strip=True)

                                    classroom = locationTag.string.strip()
                                    Location = classroom + " " + campus

                        # Extract Meeting Time
                        Date = cols[1].contents[0].get_text(strip=True).split("\n")
                        Date = [str(date).strip() for date in Date]
                        if len(Date) > 2:
                            Date.pop(2)
                            Date = " ".join(Date)
                        elif Date[0] == "APPT" and locationTag == "ONLNE CRSE":
                            try:
                                Date = cols[1].find("strong").string
                            except:
                                Date = "N/A"
                        else:
                            Date = "N/A"

                        # Update classSchedule with time & location
                        classSchedule.update({"MeetingTime": Date, "Location": Location})

                    # If we have both classNumber and classSchedule filled, save it
                    if classNumber and "MeetingTime" in classSchedule and "Location" in classSchedule:
                        classList[classNumber] = classSchedule
                        classSchedule = {}  # Reset for next section

                # Store final class list
                course.update({"Sections": classList})

            elif i % 5 == 0:
                classInfo.append(course.copy())
                course.clear()
            i += 1
        except Exception as e:
            print(f"Error with {classSection}: {e}")
            continue
    return classInfo
    #with open("courseDatabase.json","w") as file:
    #    json.dump(classInfo, file, indent=4)

