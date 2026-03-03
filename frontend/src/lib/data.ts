import { Course, Semester } from "./types";

const API_BASE = (import.meta as any).env?.VITE_API_BASE ?? "http://localhost:5000";

export async function listSemesters(): Promise<Semester[]> {
  const res = await fetch(`${API_BASE}/api/v1/semesters`);
  if (!res.ok) throw new Error(`listSemesters failed: ${res.status}`);
  const json = await res.json();
  return json.data as Semester[];
}

export async function searchCourses({
  semesterId,
  query,
}: {
  semesterId: string;
  query: string;
}): Promise<Course[]> {
  const params = new URLSearchParams({ semesterId, query });
  const res = await fetch(`${API_BASE}/api/v1/courses/search?${params}`);
  if (!res.ok) throw new Error(`searchCourses failed: ${res.status}`);
  const json = await res.json();
  return json.data as Course[];
}

export async function getCourseById({
  semesterId,
  courseId,
}: {
  semesterId: string;
  courseId: string;
}): Promise<Course | undefined> {
  const params = new URLSearchParams({ semesterId });
  const res = await fetch(
    `${API_BASE}/api/v1/courses/${encodeURIComponent(courseId)}?${params}`
  );
  if (res.status === 404) return undefined;
  if (!res.ok) throw new Error(`getCourseById failed: ${res.status}`);
  const json = await res.json();
  return json.data as Course;
}
