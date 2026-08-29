/**
 * Mock/demo data for the Student Dashboard foundation. Skills, Assessments,
 * Applications, Jobs, Internships, Learning, and AI recommendations have no
 * real backing system yet (see docs/PROJECT_CONTEXT.md §12/§15) — every
 * export here is placeholder data, not a database or API read.
 *
 * Kept deliberately separate from database logic, auth, and the Supabase
 * client: when a real API/table backs one of these, only this file (and
 * the fetch call site) needs to change — the types below are the contract
 * dashboard components already render against.
 */

export interface DashboardKpi {
  id: "skillScore" | "careerReadiness" | "learningProgress" | "applications" | "achievements";
  label: string;
  value: string;
  helperText: string;
  trend: "up" | "down" | "neutral";
}

export const MOCK_KPIS: DashboardKpi[] = [
  { id: "skillScore", label: "Overall Skill Score", value: "78%", helperText: "Good", trend: "up" },
  { id: "careerReadiness", label: "Career Readiness", value: "72%", helperText: "Improving", trend: "up" },
  { id: "learningProgress", label: "Learning Progress", value: "64%", helperText: "Continue Learning", trend: "neutral" },
  { id: "applications", label: "Applications", value: "12", helperText: "4 Shortlisted", trend: "neutral" },
  { id: "achievements", label: "Achievements", value: "8", helperText: "Badges earned", trend: "neutral" },
];

export interface SkillRadarPoint {
  category: string;
  score: number;
}

export const MOCK_SKILL_RADAR: SkillRadarPoint[] = [
  { category: "Programming", score: 82 },
  { category: "Problem Solving", score: 75 },
  { category: "Database", score: 60 },
  { category: "Communication", score: 68 },
  { category: "Teamwork", score: 85 },
  { category: "Leadership", score: 55 },
];

export interface SkillProficiency {
  name: string;
  level: number;
}

export const MOCK_SKILL_LIST: SkillProficiency[] = [
  { name: "Python", level: 85 },
  { name: "SQL", level: 70 },
  { name: "React", level: 65 },
  { name: "JavaScript", level: 75 },
  { name: "FastAPI", level: 55 },
  { name: "Communication", level: 68 },
];

export interface DashboardEvent {
  id: string;
  title: string;
  type: "assessment" | "workshop" | "drive" | "announcement";
  date: string;
}

export const MOCK_EVENTS: DashboardEvent[] = [
  { id: "e1", title: "Data Structures Skill Assessment", type: "assessment", date: "Tomorrow, 10:00 AM" },
  { id: "e2", title: "Resume Building Workshop", type: "workshop", date: "Friday, 3:00 PM" },
  { id: "e3", title: "Campus Internship Drive", type: "drive", date: "Next Monday" },
  { id: "e4", title: "New skill assessments now available", type: "announcement", date: "Just posted" },
];

export type RecommendationCategory = "internships" | "jobs" | "courses" | "projects";

export interface RecommendationItem {
  id: string;
  title: string;
  organization: string;
  location: string;
  mode: "Remote" | "Hybrid" | "On-site";
  duration?: string;
  compensation?: string;
  matchPercent: number;
}

export const MOCK_RECOMMENDATIONS: Record<RecommendationCategory, RecommendationItem[]> = {
  internships: [
    { id: "i1", title: "Software Engineering Intern", organization: "Nimbus Systems", location: "Bengaluru", mode: "Hybrid", duration: "6 months", compensation: "₹25,000/mo", matchPercent: 91 },
    { id: "i2", title: "Backend Developer Intern", organization: "Verdant Labs", location: "Remote", mode: "Remote", duration: "3 months", compensation: "₹20,000/mo", matchPercent: 86 },
    { id: "i3", title: "Data Science Intern", organization: "Orbit Analytics", location: "Pune", mode: "On-site", duration: "6 months", compensation: "₹22,000/mo", matchPercent: 78 },
  ],
  jobs: [
    { id: "j1", title: "Junior Frontend Developer", organization: "Brightline Tech", location: "Hyderabad", mode: "Hybrid", compensation: "₹6-8 LPA", matchPercent: 82 },
    { id: "j2", title: "Associate Data Analyst", organization: "Northgate Analytics", location: "Remote", mode: "Remote", compensation: "₹5-7 LPA", matchPercent: 74 },
  ],
  courses: [
    { id: "c1", title: "Advanced React Patterns", organization: "AIC Learning", location: "Online", mode: "Remote", duration: "4 weeks", matchPercent: 88 },
    { id: "c2", title: "AWS Cloud Essentials", organization: "AIC Learning", location: "Online", mode: "Remote", duration: "3 weeks", matchPercent: 80 },
  ],
  projects: [
    { id: "p1", title: "Open-Source Skill Matching Engine", organization: "AIC Community", location: "Remote", mode: "Remote", matchPercent: 76 },
  ],
};

export interface AiRecommendation {
  id: string;
  title: string;
  reason: string;
}

export const MOCK_AI_RECOMMENDATIONS: AiRecommendation[] = [
  { id: "a1", title: "Improve Docker Skills", reason: "Frequently required in your matched internships" },
  { id: "a2", title: "Complete AWS Essentials", reason: "Boosts your cloud readiness score" },
  { id: "a3", title: "React Advanced Course", reason: "Aligned with your frontend career goal" },
];

export interface ApplicationStage {
  label: string;
  count: number;
}

export const MOCK_APPLICATION_STAGES: ApplicationStage[] = [
  { label: "Applied", count: 12 },
  { label: "Under Review", count: 6 },
  { label: "Shortlisted", count: 4 },
  { label: "Interview", count: 2 },
  { label: "Selected", count: 1 },
];
