import { api } from "@/lib/api";
import type { JobRole, SkillGapAnalysis, SkillGapJobRoleAnalysis, TargetJobRole } from "@/types/skill-gap";

/**
 * Talks to the live Skill Gap API (backend/app/api/skill_gap.py). Only
 * place in the frontend that constructs these requests -- components
 * call these functions, never `api.get/put/delete` directly. Every call
 * goes through lib/api.ts's apiFetch(), which attaches the student's own
 * Supabase access token; no student_id is ever sent -- the backend
 * derives it from the token.
 *
 * The gap/readiness/priority/recommendation calculation itself lives
 * entirely on the backend (app.services.skill_gap_service) -- nothing
 * here recomputes any of it.
 */

export function listJobRoles(): Promise<{ job_roles: JobRole[] }> {
  return api.get("/api/v1/job-roles");
}

/** The caller's own analysis: against their saved target role if one is
 * set (mode: "JOB_ROLE"), otherwise the personal analysis
 * (mode: "PERSONAL"). Always check `.mode` before rendering. */
export function getSkillGap(): Promise<SkillGapAnalysis> {
  return api.get("/api/v1/skill-gap");
}

/** Analyze against any active job role, independent of the student's
 * saved target -- not currently used for a "preview before committing"
 * flow, but kept available for that. */
export function getSkillGapForJobRole(jobRoleId: string): Promise<SkillGapJobRoleAnalysis> {
  return api.get(`/api/v1/skill-gap/job-role/${jobRoleId}`);
}

/** Sets (or replaces) the caller's own target role. Only ever sends
 * job_role_id -- SetTargetJobRoleRequest rejects any other field. */
export function setTargetJobRole(jobRoleId: string): Promise<TargetJobRole> {
  return api.put("/api/v1/student/target-job-role", { job_role_id: jobRoleId });
}

/** Clears the caller's own target role. 204 No Content -- apiFetch()
 * already turns that into `undefined`. */
export function clearTargetJobRole(): Promise<void> {
  return api.delete("/api/v1/student/target-job-role");
}
