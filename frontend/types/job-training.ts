/**
 * Mirrors backend/app/schemas/job_training.py -- field-for-field, same
 * nullability.
 *
 * Job Training is the post-selection experience for a student SELECTED for
 * a JOB whose industry has authored a training program
 * (database/migrations/052_job_training.sql). It is COMPLETELY separate
 * from:
 *   - the universal Learning & Courses catalog (/student/learning), and
 *   - the Internship Workspace (/student/my-internships), which is what a
 *     SELECTED *internship* candidate uses.
 *
 * The authoritative signal that a student HAS Job Training is a
 * non-revoked enrollment returned by GET /api/v1/student/job-training --
 * never `application.status === "SELECTED"` on its own (a selected job
 * with no authored program produces no enrollment).
 */

export type JobTrainingEnrollmentStatus = "ACTIVE" | "COMPLETED" | "REVOKED";

/** Friendly label -- the backend value is never changed, only presented.
 * REVOKED is never surfaced (the list omits it, the detail 404s). */
export const JOB_TRAINING_ENROLLMENT_STATUS_LABEL: Record<
  JobTrainingEnrollmentStatus,
  string
> = {
  ACTIVE: "Active",
  COMPLETED: "Completed",
  REVOKED: "Revoked",
};

export interface JobTrainingEnrollmentSummary {
  enrollment_id: string;
  application_id: string;
  job_id: string;
  /** Best-effort: null when the job posting is no longer student-readable
   * (CLOSED / ARCHIVED). This never affects access. */
  job_title: string | null;
  /** null while the program is still a DRAFT (a student cannot read an
   * unpublished program). */
  program_id: string | null;
  program_title: string | null;
  program_status: string | null;
  enrollment_status: string;
  created_at: string | null;
  completed_at: string | null;
}

export interface JobTrainingListResponse {
  enrollments: JobTrainingEnrollmentSummary[];
}

export type JobTrainingItemType = "VIDEO" | "PDF" | "LINK" | "TEXT";

export interface StudentJobProgramItem {
  id: string;
  title: string;
  item_type: string;
  content_url: string | null;
  content_text: string | null;
  order_index: number;
}

export interface StudentJobProgramAssignment {
  id: string;
  title: string;
  description: string | null;
  instructions: string | null;
  assignment_type: string;
  is_required: boolean;
  order_index: number;
  due_offset_days: number | null;
  submission_kind: string;
  repo_required: boolean;
  live_url_expected: boolean;
  max_score: number | null;
  linked_skill_id: string | null;
}

export interface StudentJobProgramModule {
  id: string;
  title: string;
  description: string | null;
  order_index: number;
  items: StudentJobProgramItem[];
  assignments: StudentJobProgramAssignment[];
}

export interface StudentJobProgramSkill {
  skill_id: string;
  skill_name: string;
  requirement: "REQUIRED" | "OPTIONAL";
}

export interface StudentJobProgramMeta {
  id: string;
  job_id: string;
  title: string;
  summary: string | null;
  estimated_weeks: number | null;
  /** Always "PUBLISHED" in a successful detail response. */
  status: string;
  published_at: string | null;
}

export interface StudentJobTrainingDetail {
  enrollment: JobTrainingEnrollmentSummary;
  program: StudentJobProgramMeta;
  modules: StudentJobProgramModule[];
  skills: StudentJobProgramSkill[];
}
