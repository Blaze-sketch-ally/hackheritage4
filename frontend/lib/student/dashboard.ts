/**
 * Pure derivation helpers for the Student Dashboard.
 *
 * These functions ONLY reshape data that already comes from an existing,
 * authenticated API/table — they compute no new business logic, invent no
 * scores, and fetch nothing. Every input is the verbatim response of an
 * endpoint the app already ships:
 *   - studentSkills  -> Supabase `student_skills` (RLS, server component)
 *   - applications   -> GET /api/v1/student/applications
 *   - learning       -> GET /api/v1/student/learning/progress
 *   - attempts       -> GET /api/v1/attempts
 *   - skillGap       -> GET /api/v1/skill-gap  (canonical engine — never re-run here)
 *
 * Kept as standalone pure functions so the dashboard widgets stay thin and
 * every count shown on screen is unit-testable in isolation.
 */

import type { StudentSkill, ProficiencyLevel } from "@/lib/student/skills";
import type { StudentApplication, StudentApplicationStatus } from "@/types/student-opportunity";
import type { StudentLearningResource } from "@/types/student-learning";
import type { AttemptHistoryItem } from "@/types/assessment";
import type { SkillGapAnalysis } from "@/types/skill-gap";

// ---- Skills ----

export interface SkillsSummary {
  total: number;
  verified: number;
  byLevel: Record<ProficiencyLevel, number>;
}

export function summarizeSkills(skills: StudentSkill[]): SkillsSummary {
  const byLevel: Record<ProficiencyLevel, number> = {
    Beginner: 0,
    Intermediate: 0,
    Advanced: 0,
    Expert: 0,
  };
  let verified = 0;
  for (const s of skills) {
    if (s.proficiency_level in byLevel) byLevel[s.proficiency_level] += 1;
    if (s.is_verified) verified += 1;
  }
  return { total: skills.length, verified, byLevel };
}

// ---- Applications ----

/** Statuses that mean the application is still an open thread for the student. */
const ACTIVE_APPLICATION_STATUSES: StudentApplicationStatus[] = [
  "APPLIED",
  "UNDER_REVIEW",
  "SHORTLISTED",
  "INTERVIEW_SCHEDULED",
];

export interface ApplicationsSummary {
  total: number;
  active: number;
  selected: number;
  rejected: number;
  byStatus: Record<StudentApplicationStatus, number>;
}

export function summarizeApplications(applications: StudentApplication[]): ApplicationsSummary {
  const byStatus: Record<StudentApplicationStatus, number> = {
    APPLIED: 0,
    UNDER_REVIEW: 0,
    SHORTLISTED: 0,
    INTERVIEW_SCHEDULED: 0,
    SELECTED: 0,
    REJECTED: 0,
    WITHDRAWN: 0,
  };
  for (const a of applications) {
    if (a.status in byStatus) byStatus[a.status] += 1;
  }
  const active = ACTIVE_APPLICATION_STATUSES.reduce((n, s) => n + byStatus[s], 0);
  return {
    total: applications.length,
    active,
    selected: byStatus.SELECTED,
    rejected: byStatus.REJECTED,
    byStatus,
  };
}

// ---- Learning progress ----

export interface LearningSummary {
  total: number;
  saved: number;
  inProgress: number;
  completed: number;
}

export function summarizeLearning(rows: StudentLearningResource[]): LearningSummary {
  let saved = 0;
  let inProgress = 0;
  let completed = 0;
  for (const r of rows) {
    if (r.status === "SAVED") saved += 1;
    else if (r.status === "IN_PROGRESS") inProgress += 1;
    else if (r.status === "COMPLETED") completed += 1;
  }
  return { total: rows.length, saved, inProgress, completed };
}

// ---- Assessments ----

export interface AssessmentsSummary {
  /** COMPLETED (scored) attempts only. */
  completed: number;
  /** COMPLETED attempts whose server-computed `passed` is true. */
  passed: number;
  /** Verified a skill (server-computed) among COMPLETED attempts. */
  skillsVerified: number;
  latest: AttemptHistoryItem | null;
}

export function summarizeAssessments(attempts: AttemptHistoryItem[]): AssessmentsSummary {
  const done = attempts.filter((a) => a.status === "COMPLETED");
  return {
    completed: done.length,
    passed: done.filter((a) => a.passed === true).length,
    skillsVerified: done.filter((a) => a.skill_verified === true).length,
    // GET /attempts is documented as "most recent first".
    latest: attempts[0] ?? null,
  };
}

// ---- Career readiness (surfaces the canonical Skill Gap engine's output) ----

export type ReadinessDisplay =
  | { mode: "JOB_ROLE"; roleName: string; readinessPercentage: number; matched: number; needsImprovement: number; missing: number }
  | { mode: "PERSONAL"; totalSkills: number; verifiedSkills: number };

/**
 * Reshapes a `GET /api/v1/skill-gap` response for the dashboard KPI. The
 * `readiness_percentage` is the canonical engine's own number — this
 * function never computes a readiness figure of its own. When no target
 * role is set the engine returns PERSONAL mode, for which there is no
 * readiness percentage, so the dashboard shows honest counts instead.
 */
export function toReadinessDisplay(analysis: SkillGapAnalysis): ReadinessDisplay {
  if (analysis.mode === "JOB_ROLE") {
    return {
      mode: "JOB_ROLE",
      roleName: analysis.job_role.name,
      readinessPercentage: analysis.readiness_percentage,
      matched: analysis.summary.matched,
      needsImprovement: analysis.summary.needs_improvement,
      missing: analysis.summary.missing,
    };
  }
  return {
    mode: "PERSONAL",
    totalSkills: analysis.counts.total_active_skills,
    verifiedSkills: analysis.counts.verified_skills,
  };
}
