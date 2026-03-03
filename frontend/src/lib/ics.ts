import { ScheduledMeeting, Semester } from "./types";

// iCalendar day codes for each DayOfWeek value
const DAY_TO_ICAL: Record<string, string> = {
  M: "MO",
  T: "TU",
  W: "WE",
  Th: "TH",
  F: "FR",
  Sa: "SA",
  Su: "SU",
};

// Default semester bounds used when the Semester object has no dates.
// These are approximate; the frontend can pass real dates once they're available.
const DEFAULT_SEMESTER_WEEKS = 16;

function pad(n: number): string {
  return String(n).padStart(2, "0");
}

/** Format a Date as a UTC iCal datetime string: "YYYYMMDDTHHmmssZ" */
function toIcalDateTime(d: Date): string {
  return (
    `${d.getUTCFullYear()}${pad(d.getUTCMonth() + 1)}${pad(d.getUTCDate())}` +
    `T${pad(d.getUTCHours())}${pad(d.getUTCMinutes())}00Z`
  );
}

/** Format a Date as a local iCal date string: "YYYYMMDD" */
function toIcalDate(d: Date): string {
  return `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}`;
}

/**
 * Find the first occurrence of a given iCal weekday (e.g. "MO") on or after
 * the reference date.
 */
function firstOccurrenceOnOrAfter(icalDay: string, after: Date): Date {
  const dayNames = ["SU", "MO", "TU", "WE", "TH", "FR", "SA"];
  const targetDow = dayNames.indexOf(icalDay);
  const d = new Date(after);
  while (d.getDay() !== targetDow) {
    d.setDate(d.getDate() + 1);
  }
  return d;
}

/**
 * Build a Date in local time from a date and a "HH:MM" 24-hour time string.
 */
function dateAtTime(base: Date, time: string): Date {
  const [hh, mm] = time.split(":").map(Number);
  const d = new Date(base);
  d.setHours(hh, mm, 0, 0);
  return d;
}

/**
 * Generate an iCalendar (.ics) string from a list of scheduled meetings.
 *
 * Each ScheduledMeeting becomes a weekly recurring VEVENT. Meetings that
 * share the same componentId and day pattern are collapsed into one VEVENT
 * with a BYDAY rule covering all days.
 *
 * @param meetings  The list of ScheduledMeeting objects from the Zustand store.
 * @param semester  The active Semester (used for the calendar title).
 * @param semesterStart  Optional: first day of the semester (defaults to
 *                       next Monday from today).
 * @param semesterEnd    Optional: last day of the semester (defaults to
 *                       semesterStart + 16 weeks).
 */
export function generateICS(
  meetings: ScheduledMeeting[],
  semester: Semester,
  semesterStart?: Date,
  semesterEnd?: Date
): string {
  const now = new Date();

  // Default semester start: next Monday on or after today
  const defaultStart = new Date(now);
  while (defaultStart.getDay() !== 1) {
    defaultStart.setDate(defaultStart.getDate() + 1);
  }
  const start = semesterStart ?? defaultStart;

  // Default semester end: 16 weeks after start
  const defaultEnd = new Date(start);
  defaultEnd.setDate(defaultEnd.getDate() + DEFAULT_SEMESTER_WEEKS * 7);
  const end = semesterEnd ?? defaultEnd;

  // Group meetings by componentId so we can collapse multi-day patterns
  const byComponent = new Map<string, ScheduledMeeting[]>();
  for (const m of meetings) {
    const key = m.componentId;
    if (!byComponent.has(key)) byComponent.set(key, []);
    byComponent.get(key)!.push(m);
  }

  const uid_base = `ku-schedule-${Date.now()}`;
  const vevents: string[] = [];
  let eventIndex = 0;

  for (const [componentId, componentMeetings] of byComponent) {
    // All meetings for this component share the same startTime/endTime
    const { courseId, type, section, startTime, endTime, location, instructor } =
      componentMeetings[0];

    // Collect all iCal day codes for this component's days
    const icalDays = componentMeetings
      .map((m) => DAY_TO_ICAL[m.day])
      .filter(Boolean);
    if (icalDays.length === 0) continue;

    // Compute DTSTART: first occurrence of the first listed day on or after
    // the semester start date.
    const firstIcalDay = icalDays[0];
    const firstDate = firstOccurrenceOnOrAfter(firstIcalDay, start);
    const dtstart = dateAtTime(firstDate, startTime);
    const dtend = dateAtTime(firstDate, endTime);

    // UNTIL date: last day of the semester
    const untilDate = new Date(end);
    untilDate.setHours(23, 59, 59, 0);

    const summary = `${courseId} ${type} ${section}`;
    const description = instructor ? `Instructor: ${instructor}` : "";
    const locationStr = location ?? "";
    const uid = `${uid_base}-${eventIndex++}@ku-schedule`;
    const dtstamp = toIcalDateTime(now);

    const byDay = icalDays.join(",");
    const until = toIcalDate(end);

    vevents.push(
      [
        "BEGIN:VEVENT",
        `UID:${uid}`,
        `DTSTAMP:${dtstamp}`,
        `DTSTART;TZID=America/Chicago:${toLocalIcalDateTime(dtstart)}`,
        `DTEND;TZID=America/Chicago:${toLocalIcalDateTime(dtend)}`,
        `RRULE:FREQ=WEEKLY;BYDAY=${byDay};UNTIL=${until}`,
        `SUMMARY:${summary}`,
        description ? `DESCRIPTION:${description}` : "",
        locationStr ? `LOCATION:${locationStr}` : "",
        "END:VEVENT",
      ]
        .filter(Boolean)
        .join("\r\n")
    );
  }

  const lines = [
    "BEGIN:VCALENDAR",
    "VERSION:2.0",
    "PRODID:-//KU Schedule Builder//EN",
    "CALSCALE:GREGORIAN",
    "METHOD:PUBLISH",
    `X-WR-CALNAME:${semester.label} Schedule`,
    "X-WR-TIMEZONE:America/Chicago",
    ...vevents,
    "END:VCALENDAR",
  ];

  return lines.join("\r\n");
}

/** Format a local Date as iCal local datetime "YYYYMMDDTHHmmss" (no Z). */
function toLocalIcalDateTime(d: Date): string {
  return (
    `${d.getFullYear()}${pad(d.getMonth() + 1)}${pad(d.getDate())}` +
    `T${pad(d.getHours())}${pad(d.getMinutes())}00`
  );
}

/**
 * Trigger a browser download of the given .ics content.
 */
export function downloadICS(content: string, filename = "schedule.ics"): void {
  const blob = new Blob([content], { type: "text/calendar;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = filename;
  a.click();
  URL.revokeObjectURL(url);
}
