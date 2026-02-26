import React, { useState, useEffect } from "react";
import axios from "axios";

const CourseSearchBar = ({ onCourseSelect }) => {
    const [query, setQuery] = useState("");
    const [suggestions, setSuggestions] = useState([]);

    useEffect(() => {
        if (query.length < 2) {
            setSuggestions([]);
            return;
        }

        const fetchSuggestions = async () => {
            try {
                const response = await axios.get(`http://127.0.0.1:5000/search`, {
                    params: { query }
                });
                setSuggestions(response.data);
            } catch (error) {
                console.error("Error fetching course suggestions:", error);
            }
        };

        const debounceTimer = setTimeout(fetchSuggestions, 300);
        return () => clearTimeout(debounceTimer);
    }, [query]);

    return (
        <div className="relative w-full">
            <input
                type="text"
                placeholder="Search course..."
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                className="w-full p-2 border border-gray-500 rounded bg-gray-900 text-white"
            />
            {suggestions.length > 0 && (
                <ul className="absolute w-full bg-gray-800 border border-gray-600 rounded shadow-lg mt-1 z-50">
                    {suggestions.map((course) => (
                        <li
                            key={course.courseCode}
                            className="p-2 hover:bg-gray-700 cursor-pointer"
                            onClick={() => onCourseSelect(course)}
                        >
                            {course.courseCode} - {course.courseName}
                        </li>
                    ))}
                </ul>
            )}
        </div>
    );
};

export default CourseSearchBar;