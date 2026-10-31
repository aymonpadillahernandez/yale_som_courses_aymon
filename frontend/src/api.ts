// Calls the FastAPI backend. On Render, VITE_API_URL is set at build time.
export const API_BASE = (import.meta.env.VITE_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

// Keys match the raw rows in data/yale_courses.json, which /api/courses returns as-is.
export interface Course {
  "Course ID": string;
  "Course Number": string;
  "Course Title": string;
  "Course Category": string;
  "Course Type": string;
  "Course Description": string;
  "Course Session": string;
  "Course Session Start date": string;
  "Course Session End Date": string;
  "Faculty 1": string;
  "Faculty 1 Email": string;
  faculty_bio: string;
  Daytimes: string;
  "Timings Day": string;
  "Timings StartTime": string;
  "Timings EndTime": string;
  Room: string;
  Section: string;
  Units: string;
  "Bid Or Permission": string;
  Syllabus: string;
  "Old Syllabus": string;
  TermCode: string;
  Visible: string;
  School: string;
  "School Code": string;
  Subject: string;
  "Same As": string;
  "Source URL": string;
  Sections?: number;
}

export interface CoursesResponse {
  count: number;
  total: number;
  offset: number;
  limit: number;
  courses: Course[];
}

export interface School {
  code: string;
  name: string;
  count: number;
  categories: string[];
}

export interface SchoolsResponse {
  term: string;
  total: number;
  schools: School[];
}

export interface CourseFilters {
  q?: string;
  school?: string;
  category?: string;
  offset?: number;
  limit?: number;
}

export interface ChatResponse {
  reply: string;
  tools_used: string[];
}

async function getJson<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as T;
}

export function fetchCourses(filters: CourseFilters = {}): Promise<CoursesResponse> {
  const params = new URLSearchParams();
  Object.entries(filters).forEach(([key, value]) => {
    const text = String(value ?? "").trim();
    if (text && text !== "All") params.set(key, text);
  });
  const suffix = params.toString() ? `?${params}` : "";
  return getJson<CoursesResponse>(`/api/courses${suffix}`);
}

export function fetchSchools(): Promise<SchoolsResponse> {
  return getJson<SchoolsResponse>("/api/schools");
}

export function fetchHealth(): Promise<{ ok: boolean; courses_file: string }> {
  return getJson<{ ok: boolean; courses_file: string }>("/api/health");
}

export async function sendChat(message: string): Promise<ChatResponse> {
  const response = await fetch(`${API_BASE}/api/chat`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ message }),
  });
  if (!response.ok) {
    throw new Error(`${response.status} ${response.statusText}`);
  }
  return (await response.json()) as ChatResponse;
}
