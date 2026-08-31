import { api } from "@/lib/api";
import type { CareerRole, SkillGap } from "@/types/career-role";

/**
 * Talks to the live Career Role / Skill Gap API (backend/app/api/
 * career_roles.py -- Phase 1L). This is the only place in the frontend
 * that constructs these requests; components call these functions, never
 * `api.get` directly, matching lib/student/assessment.ts's own
 * convention. Every call goes through lib/api.ts's apiFetch(), which
 * attaches the student's own Supabase access token -- no student_id is
 * ever sent in a request; the backend derives it from the token.
 */

export function listCareerRoles(): Promise<{ career_roles: CareerRole[] }> {
  return api.get("/api/v1/career-roles");
}

export function getCareerRole(careerRoleId: string): Promise<CareerRole> {
  return api.get(`/api/v1/career-roles/${careerRoleId}`);
}

/** The authenticated student's own derived skill-gap comparison against
 * one career role -- computed fresh on every call from their real
 * completed assessment history (app.services.assessment_service.
 * get_student_skill_scores), never mocked, never cached client-side. */
export function getSkillGap(careerRoleId: string): Promise<SkillGap> {
  return api.get(`/api/v1/career-roles/${careerRoleId}/skill-gap`);
}
