import { api } from "@/lib/api";
import type { JobTrainingListResponse, StudentJobTrainingDetail } from "@/types/job-training";

/**
 * Talks to OUR student Job Training API
 * (backend/app/api/student_job_training.py,
 * /api/v1/student/job-training). Components call these functions, never
 * `api.*` directly, and NEVER Supabase directly.
 *
 * Every call goes through lib/api.ts's apiFetch(), which attaches the
 * student's own Supabase access token. No `student_id` / enrollment
 * ownership is ever sent -- the backend derives identity from the token
 * (require_student -> current_user.id) and RLS + public.student_can_access_job_program
 * are the real access-control boundary. A revoked enrollment, an
 * unpublished program, or another student's enrollment id all come back
 * as a plain 404.
 *
 * The industry-only authoring / provisioning / heal endpoints are
 * deliberately NOT wrapped here -- students never author or provision.
 */

/** The authenticated student's non-revoked Job Training enrollments. An
 * empty `enrollments` array is the authoritative "this student has no Job
 * Training" signal -- used to decide whether to show the nav item / CTA,
 * never `application.status` alone. */
export function listMyJobTraining(): Promise<JobTrainingListResponse> {
  return api.get("/api/v1/student/job-training");
}

/** One enrollment's PUBLISHED program (job info + modules + published
 * items + published assignments + skills). 404 for an inaccessible id --
 * callers must render a safe not-found state, never another student's
 * data. */
export function getMyJobTrainingEnrollment(
  enrollmentId: string,
): Promise<StudentJobTrainingDetail> {
  return api.get(`/api/v1/student/job-training/${encodeURIComponent(enrollmentId)}`);
}
