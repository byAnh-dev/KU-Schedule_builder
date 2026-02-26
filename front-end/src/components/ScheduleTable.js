import React from "react";
import { useDrag, useDrop } from "react-dnd";

// Define the item type for drag-and-drop
const ITEM_TYPE = "COURSE";

// Function to parse time from "09:30 - 10:45 AM" format
const parseTime = (timeRange) => {
    if (!timeRange) return null;

    const [start, end] = timeRange.split(" - ");
    const parseSingleTime = (time) => {
        let [hours, minutes] = time.match(/\d+/g).map(Number);
        const period = time.includes("PM") ? "PM" : "AM";
        if (period === "PM" && hours !== 12) hours += 12;
        if (period === "AM" && hours === 12) hours = 0;
        return hours + minutes / 60;
    };

    return { start: parseSingleTime(start), end: parseSingleTime(end) };
};

// Days mapping to index positions
const daysMap = { "M": 1, "T": 2, "W": 3, "R": 4, "F": 5 };

// **Course Component for Dragging**
const ScheduleItem = ({ course, section }) => {
    const [{ isDragging }, drag] = useDrag({
        type: ITEM_TYPE,
        item: { course, section },
        collect: (monitor) => ({
            isDragging: !!monitor.isDragging(),
        }),
    });

    return (
        <div
            ref={drag}
            className={`bg-blue-500 text-white p-2 rounded ${
                isDragging ? "opacity-50" : "opacity-100"
            } flex items-center justify-center`}
        >
            {course.courseCode} - {section.SectionType}
        </div>
    );
};

// **Drop Target Component**
const ScheduleSlot = ({ timeSlot, day, courses, moveCourse }) => {
    const [{ isOver }, drop] = useDrop({
        accept: ITEM_TYPE,
        drop: (item) => moveCourse(item.course, item.section, day, timeSlot),
        collect: (monitor) => ({
            isOver: !!monitor.isOver(),
        }),
    });

    return (
        <div
            ref={drop}
            className={`border p-2 min-h-16 relative ${
                isOver ? "bg-gray-700" : "bg-gray-800"
            }`}
        >
            {courses.map((c, index) => (
                <ScheduleItem key={index} course={c.course} section={c.section} />
            ))}
        </div>
    );
};

// **Main Schedule Table Component**
const ScheduleTable = ({ schedule, moveCourse }) => {
    return (
        <div className="w-2/3 p-4">
            <h2 className="text-xl mb-2 text-white">Weekly Schedule</h2>
            <div className="grid grid-cols-6 gap-2 bg-gray-800 p-4 rounded-lg text-white">
                {/* Headers for Days */}
                <div className="col-span-1 text-center">Time</div>
                <div className="col-span-1 text-center">Monday</div>
                <div className="col-span-1 text-center">Tuesday</div>
                <div className="col-span-1 text-center">Wednesday</div>
                <div className="col-span-1 text-center">Thursday</div>
                <div className="col-span-1 text-center">Friday</div>

                {/* Generate schedule grid with correct time mapping */}
                {Array.from({ length: 12 }, (_, i) => (
                    <React.Fragment key={i}>
                        {/* Time Labels on the left */}
                        <div className="text-center">{8 + i}:00</div>
                        {Array.from({ length: 5 }, (_, j) => (
                            <ScheduleSlot
                                key={j}
                                timeSlot={8 + i}
                                day={j + 1}  // Adjust for mapping
                                courses={schedule[j + 1]?.[8 + i] || []}  // ✅ Make sure schedule exists
                                moveCourse={moveCourse}
                            />
                        ))}
                    </React.Fragment>
                ))}
            </div>
        </div>
    );
};

export default ScheduleTable;
