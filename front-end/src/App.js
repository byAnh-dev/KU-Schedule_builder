import React, { useState } from "react";
import { DndProvider } from "react-dnd";
import { HTML5Backend } from "react-dnd-html5-backend";
import CourseSearchBar from "./components/CourseSearchBar";
import CourseSummary from "./components/CourseSummary";
import ScheduleTable from "./components/ScheduleTable";

const App = () => {
    const [selectedCourses, setSelectedCourses] = useState([]);
    const [schedule, setSchedule] = useState({});  // Stores time-based schedule

    // ✅ Add a selected course to the summary list
    const handleCourseSelect = (course) => {
        if (!selectedCourses.some((c) => c.courseCode === course.courseCode)) {
            setSelectedCourses([...selectedCourses, course]);
        }
    };

    // ✅ Move a course in the schedule
    const moveCourse = (course, section, day, timeSlot) => {
        setSchedule((prevSchedule) => {
            const newSchedule = { ...prevSchedule };

            if (!newSchedule[day]) {
                newSchedule[day] = {};
            }

            if (!newSchedule[day][timeSlot]) {
                newSchedule[day][timeSlot] = [];
            }

            newSchedule[day][timeSlot] = [{ course, section }];
            return newSchedule;
        });
    };

    return (
        <DndProvider backend={HTML5Backend}>
            <div className="min-h-screen bg-gray-900 text-white p-4">
                <h1 className="text-2xl mb-4">KU Schedule Builder</h1>
                
                {/* ✅ Search Bar */}
                <CourseSearchBar onCourseSelect={handleCourseSelect} />

                {/* ✅ Layout: Course Summary & Schedule */}
                <div className="flex gap-4 mt-4">
                    <CourseSummary courses={selectedCourses} />
                    <ScheduleTable schedule={schedule} moveCourse={moveCourse} />
                </div>
            </div>
        </DndProvider>
    );
};

export default App;
