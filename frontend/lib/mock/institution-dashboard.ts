/**
 * Mock/demo data for the Institution Dashboard. Student-institution
 * affiliation, placement records, and cross-student aggregation have no
 * real backing system yet (see the Phase 1L+ planning roadmap — this is
 * Phase 1O scope) — every export here is placeholder data, not a
 * database or API read. Mirrors lib/mock/student-dashboard.ts's own
 * convention exactly.
 */

export interface InstitutionKpi {
  id: "studentsAssessed" | "avgSkillScore" | "placementRate" | "industryPartners";
  label: string;
  value: string;
  helperText: string;
  trend: "up" | "down" | "neutral";
}

export const MOCK_INSTITUTION_KPIS: InstitutionKpi[] = [
  { id: "studentsAssessed", label: "Students Assessed", value: "312", helperText: "Across all skills", trend: "up" },
  { id: "avgSkillScore", label: "Avg. Skill Score", value: "71%", helperText: "Institution-wide", trend: "up" },
  { id: "placementRate", label: "Placement Rate", value: "58%", helperText: "This academic year", trend: "up" },
  { id: "industryPartners", label: "Industry Partners", value: "14", helperText: "Active collaborations", trend: "neutral" },
];

export interface PlacementTrendPoint {
  month: string;
  placed: number;
}

export const MOCK_PLACEMENT_TREND: PlacementTrendPoint[] = [
  { month: "Apr", placed: 8 },
  { month: "May", placed: 14 },
  { month: "Jun", placed: 11 },
  { month: "Jul", placed: 19 },
  { month: "Aug", placed: 26 },
];

export interface SkillGapBar {
  skill: string;
  avgScore: number;
}

export const MOCK_TOP_SKILL_GAPS: SkillGapBar[] = [
  { skill: "System Design", avgScore: 42 },
  { skill: "Docker", avgScore: 48 },
  { skill: "Cloud Computing", avgScore: 51 },
  { skill: "DSA", avgScore: 55 },
  { skill: "SQL", avgScore: 63 },
];

export interface DepartmentRow {
  id: string;
  name: string;
  students: number;
  avgSkillScore: number;
  placementRate: number;
}

export const MOCK_DEPARTMENTS: DepartmentRow[] = [
  { id: "d1", name: "Computer Science", students: 142, avgSkillScore: 76, placementRate: 68 },
  { id: "d2", name: "Information Technology", students: 98, avgSkillScore: 71, placementRate: 60 },
  { id: "d3", name: "Electronics", students: 72, avgSkillScore: 62, placementRate: 45 },
];

export interface InstitutionEvent {
  id: string;
  title: string;
  type: "assessment" | "workshop" | "drive" | "announcement";
  date: string;
}

export const MOCK_INSTITUTION_EVENTS: InstitutionEvent[] = [
  { id: "e1", title: "Campus Placement Drive — 3 companies", type: "drive", date: "Next Monday" },
  { id: "e2", title: "Industry Partnership Review", type: "announcement", date: "Thursday" },
  { id: "e3", title: "Skill Gap Workshop — Cloud Computing", type: "workshop", date: "Friday, 2:00 PM" },
];
