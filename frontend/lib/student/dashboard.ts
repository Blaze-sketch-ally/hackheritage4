/**
 * Pure derivation helpers for the Student Dashboard.
 *
 * These functions ONLY reshape data that already comes from an existing,
 * authenticated API response -- they compute no new business logic,
 * invent no scores, and fetch nothing.
 *
 * Adopted from a collaborator branch during a cross-branch integration
 * pass, trimmed to just the Learning summary this project's dashboard
 * widget (components/student/dashboard/dashboard-learning.tsx) actually
 * uses -- the source file's other summaries (skills/assessments/skill
 * gap) depended on a retired job_role/skill_gap concept this project
 * never adopted, so they were left out rather than ported unused.
 */

import type { StudentLearningResource } from "@/types/student-learning";

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
