import React, { useState, useEffect } from "react";
import axios from "axios";
import { Combobox } from "@headlessui/react";

const CourseScheduler = () => {
  const [query, setQuery] = useState("");
  const [suggestions, setSuggestions] = useState([]);
  const [selectedCourses, setSelectedCourses] = useState([]);
  const [schedule, setSchedule] = useState({});

  useEffect(() => {
    if (query.length > 1) {  // Avoid unnecessary API calls
        axios.get(`http://127.0.0.1:5000/search?query=${query}&semester=Spring 2025&level=undergrad`)
            .then(res => setSuggestions(res.data.slice(0, 3))) // Limit to 3 results
            .catch(err => console.error("Error fetching course suggestions:", err));
    } else {
        setSuggestions([]); // Clear suggestions if query is empty
    }
}, [query]);

  const addCourse = async (courseCode) => {
    if (!selectedCourses.some(course => course.CourseCode === courseCode)) {
      try {
        const response = await axios.get(`/get_course?courseCode=${courseCode}`);
        const updatedCourses = [...selectedCourses, response.data];
        setSelectedCourses(updatedCourses);
        setQuery(""); // Clear input after selection
        setSuggestions([]);

        // Update schedule
        updateSchedule(updatedCourses);

        // Send selected courses to backend for conflict checking
        axios.post("/check_conflict", { courses: updatedCourses.map(course => course.CourseCode) })
          .then(res => {
            if (res.data.error) {
              alert(res.data.error);
            }
          })
          .catch(err => console.error("Conflict check error:", err));
      } catch (error) {
        console.error("Error fetching course details", error);
      }
    }
  };

  const updateSchedule = (courses) => {
    let newSchedule = {};
    courses.forEach(course => {
      Object.values(course.Sections).forEach(section => {
        const days = section.MeetingTime.split(" ")[0]; // Extract days
        const time = section.MeetingTime.replace(days, "").trim(); // Extract time
        days.split("").forEach(day => {
          if (!newSchedule[day]) newSchedule[day] = [];
          newSchedule[day].push({
            time,
            courseCode: course.CourseCode,
            instructor: section.Instructor,
          });
        });
      });
    });
    setSchedule(newSchedule);
  };

  return (
    <div className="bg-gray-900 text-white min-h-screen p-8">
      <h1 className="text-3xl font-bold mb-4">Course Scheduler</h1>
      <div className="mb-4">
        <Combobox value={query} onChange={setQuery}>
          <Combobox.Input 
            className="w-full p-2 border rounded text-black" 
            placeholder="Search for a course (e.g., EECS 140)"
            onChange={(e) => setQuery(e.target.value)}
          />
          {suggestions.length > 0 && (
            <Combobox.Options className="bg-white text-black w-full mt-2 rounded shadow-lg absolute z-10">
              {suggestions.map((course) => (
                <Combobox.Option 
                  key={course.courseCode} 
                  value={course.courseCode}
                  onClick={() => addCourse(course.courseCode)}
                  className="p-2 cursor-pointer hover:bg-gray-200"
                >
                  {course.courseCode} - {course.courseName}
                </Combobox.Option>
              ))}
            </Combobox.Options>
          )}
        </Combobox>
      </div>

      <div>
        <h2 className="text-2xl font-semibold">Selected Courses</h2>
        {selectedCourses.length === 0 ? (
          <p>No courses selected</p>
        ) : (
          <ul className="mt-2">
            {selectedCourses.map((course, index) => (
              <li key={index} className="p-2 bg-gray-800 rounded my-2">
                <strong>{course.CourseCode}:</strong> {course.CourseName} ({course.CreditHours} credits)
              </li>
            ))}
          </ul>
        )}
      </div>
      
      {/* Schedule Table */}
      <div className="mt-6">
        <h2 className="text-2xl font-semibold">Weekly Schedule</h2>
        <div className="grid grid-cols-6 gap-2 mt-4 text-center border border-gray-700">
          <div className="bg-gray-800 p-2 font-bold">Time</div>
          {['Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday'].map(day => (
            <div key={day} className="bg-gray-800 p-2 font-bold">{day}</div>
          ))}
          {Array.from({ length: 12 }).map((_, i) => (
            <>
              <div className="p-2 border border-gray-700">{8 + i}:00 AM</div>
              {['M', 'T', 'W', 'R', 'F'].map(day => (
                <div key={`${day}-${i}`} className="p-2 border border-gray-700 h-16 bg-gray-900">
                  {schedule[day]?.find(s => s.time.includes(`${8 + i}:00`))?.courseCode || ""}
                </div>
              ))}
            </>
          ))}
        </div>
      </div>
    </div>
  );
};

export default CourseScheduler;
