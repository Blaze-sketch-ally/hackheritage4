/**
 * Mock/demo data for the Industry Dashboard. Opportunities, applications,
 * and matching have no real backing system yet (see docs/PROJECT_CONTEXT.md
 * and the Phase 1L+ planning roadmap — this is Phase 1M+ scope) — every
 * export here is placeholder data, not a database or API read. Mirrors
 * lib/mock/student-dashboard.ts's own convention exactly: kept separate
 * from auth/Supabase logic, so when a real API backs one of these, only
 * this file (and the fetch call site) needs to change.
 */

export interface IndustryKpi {
  id: "activePostings" | "totalApplicants" | "shortlisted" | "interviews";
  label: string;
  value: string;
  helperText: string;
  trend: "up" | "down" | "neutral";
}

export const MOCK_INDUSTRY_KPIS: IndustryKpi[] = [
  { id: "activePostings", label: "Active Postings", value: "6", helperText: "3 internships, 3 jobs", trend: "neutral" },
  { id: "totalApplicants", label: "Total Applicants", value: "142", helperText: "This month", trend: "up" },
  { id: "shortlisted", label: "Shortlisted", value: "24", helperText: "Awaiting interview", trend: "up" },
  { id: "interviews", label: "Interviews Scheduled", value: "9", helperText: "Next 7 days", trend: "neutral" },
];

export interface PipelineStage {
  label: string;
  count: number;
}

export const MOCK_HIRING_PIPELINE: PipelineStage[] = [
  { label: "Applied", count: 142 },
  { label: "Under Review", count: 58 },
  { label: "Shortlisted", count: 24 },
  { label: "Interview", count: 9 },
  { label: "Selected", count: 3 },
];

export interface RecentPosting {
  id: string;
  title: string;
  type: "Internship" | "Job";
  applicants: number;
  status: "Open" | "Closing Soon" | "Closed";
}

export const MOCK_RECENT_POSTINGS: RecentPosting[] = [
  { id: "p1", title: "Software Engineering Intern", type: "Internship", applicants: 38, status: "Open" },
  { id: "p2", title: "Backend Developer", type: "Job", applicants: 27, status: "Open" },
  { id: "p3", title: "Data Analyst Intern", type: "Internship", applicants: 19, status: "Closing Soon" },
  { id: "p4", title: "Frontend Developer", type: "Job", applicants: 41, status: "Open" },
];

export interface IndustryEvent {
  id: string;
  title: string;
  type: "assessment" | "workshop" | "drive" | "announcement";
  date: string;
}

export const MOCK_INDUSTRY_EVENTS: IndustryEvent[] = [
  { id: "e1", title: "Interview: Backend Developer candidates", type: "drive", date: "Tomorrow, 11:00 AM" },
  { id: "e2", title: "Campus Recruitment Drive — AIC Institute", type: "drive", date: "Friday" },
  { id: "e3", title: "New applicants for Data Analyst Intern", type: "announcement", date: "Just posted" },
];
