import React from "react";

const CourseSummary = ({ courses }) => {
    return (
        <div className="w-1/3 p-4 bg-gray-800 rounded-lg">
            <h2 className="text-xl mb-2">Selected Courses</h2>
            {courses.map((course) => (
                <div key={course.courseCode} className="mb-4 border-b pb-2">
                    <h3 className="text-lg">{course.courseCode} - {course.courseName}</h3>
                    <p><strong>Professor:</strong> {course.professor || "Unknown"}</p>
                    <p><strong>Seats Available:</strong> {course.seatAvailable}</p>
                    <p><strong>Prerequisite:</strong> {course.prerequisite || "None"}</p>
                </div>
            ))}
        </div>
    );
};

export default CourseSummary;
