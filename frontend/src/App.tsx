import { useEffect, useState } from "react";
import { DndContext, DragEndEvent, DragOverlay, useSensor, useSensors, PointerSensor, rectIntersection } from "@dnd-kit/core";
import { SearchPanel } from "./components/SearchPanel";
import { SelectedCoursesPanel } from "./components/SelectedCoursesPanel";
import { Grid } from "./components/Grid";
import { BlockTool } from "./components/BlockTool";
import { ConflictPanel } from "./components/ConflictPanel";
import { useScheduleStore, useScheduledMeetings, useConflicts } from "./store/useScheduleStore";
import { listSemesters } from "./lib/data";
import { generateICS, downloadICS } from "./lib/ics";
import { Semester, DayOfWeek } from "./lib/types";
import { getBestSection, START_HOUR, MIN_PER_CELL } from "./lib/schedule";
import { Select } from "./components/ui/select";
import { Button } from "./components/ui/button";
import { Analytics } from '@vercel/analytics/react';
import { SpeedInsights } from '@vercel/speed-insights/react';
export default function App() {
  const [semesters, setSemesters] = useState<Semester[]>([]);
  const activeSemesterId = useScheduleStore((s) => s.activeSemesterId);
  const setActiveSemesterId = useScheduleStore((s) => s.setActiveSemesterId);
  const selectedCourses = useScheduleStore((s) => s.selectedCourses);
  const setLectureSection = useScheduleStore((s) => s.setLectureSection);
  const setLabSection = useScheduleStore((s) => s.setLabSection);
  const blockedTimes = useScheduleStore((s) => s.blockedTimeBySemesterId[activeSemesterId]) || [];
  const scheduledMeetings = useScheduledMeetings();
  const conflicts = useConflicts();

  const [activeDragCourseId, setActiveDragCourseId] = useState<string | null>(null);
  const [activeDragType, setActiveDragType] = useState<"LEC" | "LAB" | null>(null);
  const [hoveredDay, setHoveredDay] = useState<DayOfWeek | null>(null);
  const [hoveredTime, setHoveredTime] = useState<number | null>(null);

  const sensors = useSensors(
    useSensor(PointerSensor, {
      activationConstraint: {
        distance: 5,
      },
    })
  );

  useEffect(() => {
    listSemesters().then((loaded) => {
      setSemesters(loaded);
      // If the persisted semester ID is missing or not in the loaded list,
      // default to the first available semester.
      if (loaded.length > 0) {
        const ids = loaded.map((s) => s.id);
        if (!activeSemesterId || !ids.includes(activeSemesterId)) {
          setActiveSemesterId(loaded[loaded.length - 1].id);
        }
      }
    });
  }, []);

  const handleSemesterChange = (e: React.ChangeEvent<HTMLSelectElement>) => {
    const newId = e.target.value;
    if (selectedCourses.length > 0) {
      if (window.confirm("Switching semester will clear current selection. Continue?")) {
        setActiveSemesterId(newId);
      }
    } else {
      setActiveSemesterId(newId);
    }
  };

  const handleDragStart = (event: any) => {
    setActiveDragCourseId(event.active.data.current?.courseId || null);
    setActiveDragType(event.active.data.current?.type || "LEC");
  };

  const handleDragOver = (event: any) => {
    const { over } = event;
    if (over && over.id.toString().startsWith("slot-")) {
      setHoveredDay(over.data.current?.day as DayOfWeek);
      const index = over.data.current?.index as number;
      setHoveredTime(START_HOUR * 60 + index * MIN_PER_CELL);
    } else {
      setHoveredDay(null);
      setHoveredTime(null);
    }
  };

  const handleDragEnd = (event: DragEndEvent) => {
    setActiveDragCourseId(null);
    setActiveDragType(null);
    setHoveredDay(null);
    setHoveredTime(null);
    const { active, over } = event;

    if (over && over.id.toString().startsWith("slot-")) {
      const dropDay = over.data.current?.day as DayOfWeek;
      const index = over.data.current?.index as number;
      const dropTime = START_HOUR * 60 + index * MIN_PER_CELL;
      const courseId = active.data.current?.courseId as string;
      const type = active.data.current?.type as "LEC" | "LAB";
      
      const course = selectedCourses.find((c) => c.id === courseId);
      if (course) {
        const isLecTarget = type === "LEC";
        const otherMeetings = scheduledMeetings.filter(m => m.courseId !== course.id || (isLecTarget ? m.type !== "LEC" : m.type === "LEC"));
        const bestSection = getBestSection(course, type, dropDay, dropTime, otherMeetings, blockedTimes);
        if (bestSection) {
          if (isLecTarget) {
            setLectureSection(course.id, bestSection.id);
          } else {
            setLabSection(course.id, bestSection.id);
          }
        }
      }
    }
  };

  return (
    <DndContext 
      sensors={sensors} 
      collisionDetection={rectIntersection}
      onDragStart={handleDragStart} 
      onDragOver={handleDragOver} 
      onDragEnd={handleDragEnd}
    >
      <div className="h-screen bg-portal-bg text-portal-text font-sans flex flex-col overflow-y-auto xl:overflow-hidden">
        
        <header className="flex-none flex justify-between items-center bg-portal-surface p-4 border-b border-portal-border">
          <h1 className="text-[22px] font-serif font-bold text-portal-title m-0">Schedule Builder</h1>
          <div className="flex items-center gap-3">
            <span className="text-[14px] text-portal-text-secondary">Semester:</span>
            <Select value={activeSemesterId} onChange={handleSemesterChange} className="w-48">
              {semesters.map((s) => (
                <option key={s.id} value={s.id}>{s.label}</option>
              ))}
            </Select>
            <Button
              variant="outline"
              size="sm"
              disabled={scheduledMeetings.length === 0}
              onClick={() => {
                const sem = semesters.find((s) => s.id === activeSemesterId);
                if (!sem) return;
                const ics = generateICS(scheduledMeetings, sem);
                downloadICS(ics, `${sem.id}-schedule.ics`);
              }}
            >
              Export .ics
            </Button>
          </div>
        </header>

     <Analytics mode="production" />
     <SpeedInsights />
        <div className="flex-1 min-h-0 p-[8px] flex flex-col">
          <div className="flex flex-col xl:flex-row gap-4 w-full flex-1 min-h-0">
            
            {/* Left Sidebar */}
            <div className="w-full xl:w-[400px] flex-none flex flex-col gap-4 xl:overflow-y-auto pr-2">
              <div className="bg-portal-surface border border-portal-border rounded-none flex flex-col shadow-md">
                <div className="h-[40px] bg-portal-header border-b border-portal-border flex items-center px-[12px]">
                  <h2 className="text-[18px] font-serif font-bold text-portal-title m-0">Time Blocks</h2>
                </div>
                <div className="p-[12px]">
                  <BlockTool />
                </div>
              </div>

              <div className="bg-portal-surface border border-portal-border rounded-none flex-1 flex flex-col min-h-[300px] shadow-md">
                <div className="h-[40px] bg-portal-header border-b border-portal-border flex items-center px-[12px]">
                  <h2 className="text-[18px] font-serif font-bold text-portal-title m-0">Selected Courses</h2>
                </div>
                <div className="p-[12px] flex-1 overflow-y-auto">
                  <SelectedCoursesPanel />
                </div>
              </div>
            </div>

            {/* Right Content */}
            <div className="flex-1 flex flex-col gap-4 xl:overflow-hidden">
              
              <div className="bg-portal-surface border border-portal-border rounded-none flex flex-col flex-none shadow-md">
                <div className="h-[40px] bg-portal-header border-b border-portal-border flex justify-between items-center px-[12px]">
                  <h2 className="text-[18px] font-serif font-bold text-portal-title m-0">Search Courses</h2>
                  <div className="flex items-center gap-2">
                    {conflicts.length === 0 ? (
                      <span className="text-portal-text-secondary text-[12px]">No conflicts detected.</span>
                    ) : (
                      <span className="text-portal-danger font-bold text-[12px]">{conflicts.length} Conflict{conflicts.length > 1 ? "s" : ""} detected</span>
                    )}
                  </div>
                </div>
                <div className="p-[12px] flex flex-col gap-4">
                  <SearchPanel />
                  <ConflictPanel />
                </div>
              </div>

              <div className="bg-portal-surface border border-portal-border rounded-none flex-1 flex flex-col min-h-[600px] xl:min-h-0 xl:overflow-hidden shadow-md">
                <div className="h-[40px] bg-portal-header border-b border-portal-border flex items-center px-[12px]">
                  <h2 className="text-[18px] font-serif font-bold text-portal-title m-0">Weekly Schedule</h2>
                </div>
                <div className="p-[12px] flex-1 overflow-hidden">
                  <Grid activeDragCourseId={activeDragCourseId} activeDragType={activeDragType} hoveredDay={hoveredDay} hoveredTime={hoveredTime} />
                </div>
              </div>

            </div>
          </div>
        </div>

        <footer className="flex-none flex items-center justify-center gap-1.5 py-2 border-t border-portal-border text-[11px] text-portal-text-secondary bg-portal-header">
          <span>Found a bug?</span>
          <a
            href="https://github.com/byAnh-dev/KU-Schedule_builder/issues/new"
            target="_blank"
            rel="noopener noreferrer"
            className="text-portal-blue hover:underline font-semibold"
          >
            Report it on GitHub
          </a>
          <span>or</span>
          <a
            href="mailto:anh.hoang@ku.edu"
            className="text-portal-blue hover:underline font-semibold"
          >
            email me
          </a>
        </footer>
      </div>

      <DragOverlay>
        {activeDragCourseId ? (
          <div className={`text-[12px] text-white border-2 p-2 text-center font-bold w-48 opacity-[0.92] cursor-grabbing ${activeDragType === "LEC" ? "bg-portal-blue border-portal-blue" : "bg-portal-utility border-portal-utility"}`}>
            {activeDragCourseId}: Drag {activeDragType}
          </div>
        ) : null}
      </DragOverlay>
    </DndContext>
  );
}
