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
import type { InternshipWorkspaceSummary } from "@/types/internship-workspace";
import type { ProjectApplication } from "@/types/project-application";
import type { TrainingApplication } from "@/types/training-application";
import type { WorkshopApplication } from "@/types/workshop-application";
import { opportunityHref } from "@/types/student-notification";

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

// ---- Next actions (Phase 3) ----
//
// Every input here is the verbatim response of an endpoint already used
// elsewhere in the Student Portal (Phase 1's opportunity/participation
// detail pages, the "My Applications" tabs) -- this function fetches
// nothing and invents no status/eligibility rule beyond what those
// existing views already apply (WORKSPACE_ELIGIBLE-style sets). Job
// Training is deliberately excluded: DashboardJobTraining already covers
// that case, and duplicating it here would create two competing cards for
// the same event.

export interface NextAction {
  key: string;
  kind: "interview" | "workspace";
  title: string;
  subtitle: string;
  ctaLabel: string;
  href: string;
}

const PROJECT_WORKSPACE_STATUSES = new Set(["SELECTED", "ACTIVE"]);
const TRAINING_WORKSPACE_STATUSES = new Set(["ACCEPTED"]);
const WORKSHOP_WORKSPACE_STATUSES = new Set(["ACCEPTED"]);

function formatInterviewWhen(iso: string): string {
  const parsed = new Date(iso);
  if (Number.isNaN(parsed.getTime())) return "Interview scheduled";
  return `Interview: ${parsed.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  })}`;
}

/**
 * Up to 3 genuinely actionable items, highest priority first:
 *   1. Upcoming (live, scheduled) interviews -- soonest first.
 *   2. Selected/accepted opportunities that now have an open workspace
 *      (Internship, Project, Training, Workshop), in that fixed order.
 * Every destination reuses an existing Phase 1/2 route -- no new routing
 * logic, no per-item network request (all five inputs are already
 * O(1) list endpoints the dashboard/detail pages already call).
 */
export function buildNextActions(input: {
  applications: StudentApplication[];
  internshipWorkspaces: InternshipWorkspaceSummary[];
  projectApplications: ProjectApplication[];
  trainingApplications: TrainingApplication[];
  workshopApplications: WorkshopApplication[];
}): NextAction[] {
  const interviews: NextAction[] = input.applications
    .filter((a) => a.status === "INTERVIEW_SCHEDULED" && a.interview != null && a.opportunity != null)
    .sort((a, b) => Date.parse(a.interview!.scheduled_at) - Date.parse(b.interview!.scheduled_at))
    .map((a) => ({
      key: `interview-${a.id}`,
      kind: "interview" as const,
      title: a.opportunity!.title ?? "Upcoming interview",
      subtitle: formatInterviewWhen(a.interview!.scheduled_at),
      ctaLabel: "View Interview Details",
      href: opportunityHref(a.opportunity!.source_type, a.opportunity!.id),
    }));

  const workspaceByApplicationId = new Map(input.internshipWorkspaces.map((w) => [w.application_id, w]));
  const internshipActions: NextAction[] = [];
  for (const a of input.applications) {
    if (a.status !== "SELECTED" || a.opportunity_type !== "INTERNSHIP") continue;
    const workspace = workspaceByApplicationId.get(a.id);
    if (!workspace) continue;
    internshipActions.push({
      key: `internship-${a.id}`,
      kind: "workspace",
      title: a.opportunity?.title ?? "Internship",
      subtitle: "Your internship workspace is ready.",
      ctaLabel: "Open Internship Workspace",
      href: `/student/my-internships/${workspace.id}`,
    });
  }

  const projectActions: NextAction[] = input.projectApplications
    .filter((a) => PROJECT_WORKSPACE_STATUSES.has(a.status))
    .map((a) => ({
      key: `project-${a.id}`,
      kind: "workspace" as const,
      title: a.project?.title ?? "Project",
      subtitle: "Your project workspace is ready.",
      ctaLabel: "Open Project Workspace",
      href: `/student/industry-projects/${a.project_id}/workspace`,
    }));

  const trainingActions: NextAction[] = input.trainingApplications
    .filter((a) => TRAINING_WORKSPACE_STATUSES.has(a.status))
    .map((a) => ({
      key: `training-${a.id}`,
      kind: "workspace" as const,
      title: a.training?.title ?? "Training program",
      subtitle: "Your training workspace is ready.",
      ctaLabel: "Open Training Workspace",
      href: `/student/trainings/${a.training_id}/workspace`,
    }));

  const workshopActions: NextAction[] = input.workshopApplications
    .filter((a) => WORKSHOP_WORKSPACE_STATUSES.has(a.status))
    .map((a) => ({
      key: `workshop-${a.id}`,
      kind: "workspace" as const,
      title: a.workshop?.title ?? "Workshop",
      subtitle: "Your workshop workspace is ready.",
      ctaLabel: "Open Workshop Workspace",
      href: `/student/workshops/${a.workshop_id}/workspace`,
    }));

  return [...interviews, ...internshipActions, ...projectActions, ...trainingActions, ...workshopActions].slice(
    0,
    3,
  );
}
