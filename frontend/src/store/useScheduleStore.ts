import { useMemo } from "react";
import { create } from "zustand";
import { persist, createJSONStorage } from "zustand/middleware";
import { BlockedTime, Course, CourseComponent, DayOfWeek, ScheduledMeeting, Conflict } from "../lib/types";
import { timeToMinutes } from "../lib/schedule";

interface ScheduleState {
  activeSemesterId: string;
  selectedCourses: Course[];
  selectedLectureSectionByCourseId: Record<string, string>;
  selectedLabSectionByCourseId: Record<string, string | null>;
  blockedTimeBySemesterId: Record<string, BlockedTime[]>;
  isBlockingMode: boolean;

  setActiveSemesterId: (id: string) => void;
  setIsBlockingMode: (val: boolean) => void;
  addCourse: (course: Course) => void;
  removeCourse: (courseId: string) => void;
  setLectureSection: (courseId: string, sectionId: string) => void;
  setLabSection: (courseId: string, sectionId: string | null) => void;
  addBlockedTime: (semesterId: string, blockedTime: BlockedTime) => void;
  removeBlockedTime: (semesterId: string, blockedTimeId: string) => void;
  clearSelectedCourses: () => void;
}

export const useScheduleStore = create<ScheduleState>()(
  persist(
    (set) => ({
      activeSemesterId: "",
      selectedCourses: [],
      selectedLectureSectionByCourseId: {},
      selectedLabSectionByCourseId: {},
      blockedTimeBySemesterId: {},
      isBlockingMode: false,

      setActiveSemesterId: (id) =>
        set((state) => {
          if (state.activeSemesterId !== id) {
            return {
              activeSemesterId: id,
              selectedCourses: [],
              selectedLectureSectionByCourseId: {},
              selectedLabSectionByCourseId: {},
            };
          }
          return { activeSemesterId: id };
        }),

      setIsBlockingMode: (val) => set({ isBlockingMode: val }),

      addCourse: (course) =>
        set((state) => {
          if (state.selectedCourses.some((c) => c.id === course.id)) return state;

          const lecSections = course.components.filter((c) => c.type === "LEC");
          const defaultLec = lecSections.length > 0 ? lecSections[0].id : "";

          return {
            selectedCourses: [...state.selectedCourses, course],
            selectedLectureSectionByCourseId: {
              ...state.selectedLectureSectionByCourseId,
              [course.id]: defaultLec,
            },
            selectedLabSectionByCourseId: {
              ...state.selectedLabSectionByCourseId,
              [course.id]: null,
            },
          };
        }),

      removeCourse: (courseId) =>
        set((state) => {
          const newSelectedCourses = state.selectedCourses.filter((c) => c.id !== courseId);
          const newLec = { ...state.selectedLectureSectionByCourseId };
          const newLab = { ...state.selectedLabSectionByCourseId };
          delete newLec[courseId];
          delete newLab[courseId];

          return {
            selectedCourses: newSelectedCourses,
            selectedLectureSectionByCourseId: newLec,
            selectedLabSectionByCourseId: newLab,
          };
        }),

      setLectureSection: (courseId, sectionId) =>
        set((state) => ({
          selectedLectureSectionByCourseId: {
            ...state.selectedLectureSectionByCourseId,
            [courseId]: sectionId,
          },
        })),

      setLabSection: (courseId, sectionId) =>
        set((state) => ({
          selectedLabSectionByCourseId: {
            ...state.selectedLabSectionByCourseId,
            [courseId]: sectionId,
          },
        })),

      addBlockedTime: (semesterId, blockedTime) =>
        set((state) => {
          const current = state.blockedTimeBySemesterId[semesterId] || [];
          return {
            blockedTimeBySemesterId: {
              ...state.blockedTimeBySemesterId,
              [semesterId]: [...current, blockedTime],
            },
          };
        }),

      removeBlockedTime: (semesterId, blockedTimeId) =>
        set((state) => {
          const current = state.blockedTimeBySemesterId[semesterId] || [];
          return {
            blockedTimeBySemesterId: {
              ...state.blockedTimeBySemesterId,
              [semesterId]: current.filter((b) => b.id !== blockedTimeId),
            },
          };
        }),

      clearSelectedCourses: () =>
        set({
          selectedCourses: [],
          selectedLectureSectionByCourseId: {},
          selectedLabSectionByCourseId: {},
        }),
    }),
    {
      name: "schedule-storage",
      storage: createJSONStorage(() => localStorage),
    }
  )
);

export const useScheduledMeetings = (): ScheduledMeeting[] => {
  const selectedCourses = useScheduleStore((s) => s.selectedCourses);
  const selectedLectureSectionByCourseId = useScheduleStore((s) => s.selectedLectureSectionByCourseId);
  const selectedLabSectionByCourseId = useScheduleStore((s) => s.selectedLabSectionByCourseId);

  return useMemo(() => {
    const meetings: ScheduledMeeting[] = [];

    selectedCourses.forEach((course) => {
      const lecId = selectedLectureSectionByCourseId[course.id];
      const labId = selectedLabSectionByCourseId[course.id];

      const addComponentMeetings = (compId: string | null) => {
        if (!compId) return;
        const comp = course.components.find((c) => c.id === compId);
        if (!comp) return;

        comp.meetings.forEach((m) => {
          m.days.forEach((day) => {
            meetings.push({
              id: `${course.id}-${comp.id}-${day}-${m.startTime}`,
              courseId: course.id,
              componentId: comp.id,
              type: comp.type,
              section: comp.section,
              day,
              startTime: m.startTime,
              endTime: m.endTime,
              startMinutes: timeToMinutes(m.startTime),
              endMinutes: timeToMinutes(m.endTime),
              location: comp.location,
              instructor: comp.instructor,
            });
          });
        });
      };

      addComponentMeetings(lecId);
      addComponentMeetings(labId);
    });

    return meetings;
  }, [selectedCourses, selectedLectureSectionByCourseId, selectedLabSectionByCourseId]);
};

const EMPTY_BLOCKED_TIMES: BlockedTime[] = [];

export const useConflicts = (): Conflict[] => {
  const meetings = useScheduledMeetings();
  const activeSemesterId = useScheduleStore((s) => s.activeSemesterId);
  const blockedTimes = useScheduleStore((s) => s.blockedTimeBySemesterId[activeSemesterId]) || EMPTY_BLOCKED_TIMES;

  return useMemo(() => {
    const conflicts: Conflict[] = [];

    // Check meeting vs meeting
    for (let i = 0; i < meetings.length; i++) {
      const m1 = meetings[i];
      for (let j = i + 1; j < meetings.length; j++) {
        const m2 = meetings[j];

        if (
          m1.day === m2.day &&
          m1.startMinutes < m2.endMinutes &&
          m2.startMinutes < m1.endMinutes
        ) {
          conflicts.push({
            id: `conflict-course-${m1.id}-${m2.id}`,
            type: "course-course",
            message: `${m1.courseId} ${m1.type} ${m1.section} overlaps ${m2.courseId} ${m2.type} ${m2.section} on ${m1.day} ${m1.startTime}-${m1.endTime}`,
            item1Id: m1.id,
            item2Id: m2.id,
          });
        }
      }

      // Check meeting vs blocked time
      for (const bt of blockedTimes) {
        const btStart = timeToMinutes(bt.startTime);
        const btEnd = timeToMinutes(bt.endTime);

        if (
          m1.day === bt.day &&
          m1.startMinutes < btEnd &&
          btStart < m1.endMinutes
        ) {
          conflicts.push({
            id: `conflict-blocked-${m1.id}-${bt.id}`,
            type: "course-blocked",
            message: `${m1.courseId} ${m1.type} ${m1.section} overlaps Blocked Time on ${m1.day} ${bt.startTime}-${bt.endTime}`,
            item1Id: m1.id,
            item2Id: bt.id,
          });
        }
      }
    }

    return conflicts;
  }, [meetings, blockedTimes]);
};
