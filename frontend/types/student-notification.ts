// Mirrors backend/app/schemas/student_notification.py and
// database/migrations/035_student_notifications.sql. Keep in sync.
//
// Notifications are produced by trusted system-context code (there is no
// insert policy on the table). The frontend only lists them, marks them
// read/unread, and reads the unread count. It never creates one.

export const NOTIFICATION_TYPES = [
  "APPLICATION_STATUS",
  "INTERVIEW",
  "ASSESSMENT",
  "LEARNING",
  "MENTORSHIP",
  "EVENT",
  "SYSTEM",
  "INTERNSHIP",
  // Added by migration 052 (job training). Emitted by
  // notification_producer.emit_job_training_completed.
  "JOB_TRAINING",
] as const;
export type NotificationType = (typeof NOTIFICATION_TYPES)[number];

export const RELATED_ENTITY_TYPES = [
  "APPLICATION",
  "INTERVIEW",
  "ASSESSMENT",
  "LEARNING_RESOURCE",
  "MENTORSHIP",
  "EVENT",
  "INTERNSHIP_WORKSPACE",
  // Added by migration 052 (job training) -- the id is a
  // job_training_enrollments.id; see relatedHref() below.
  "JOB_TRAINING_ENROLLMENT",
  // Added by migration 058 -- the id is an industry_workshops.id /
  // industry_projects.id (the posting, not the application row).
  "WORKSHOP",
  "PROJECT",
  // Added by migration 060 -- the id is an industry_training.id.
  "TRAINING",
  // Added by migration 066 -- the id is a participation_workspaces.id
  // (Project/Training/Workshop assignment/submission/feedback/
  // recommendation/evaluation/completion events; see
  // notification_producer.emit_participation_*).
  "PARTICIPATION_WORKSPACE",
] as const;
export type RelatedEntityType = (typeof RELATED_ENTITY_TYPES)[number];

export interface StudentNotification {
  id: string;
  type: NotificationType;
  title: string;
  body: string;
  related_entity_type: RelatedEntityType | null;
  related_entity_id: string | null;
  is_read: boolean;
  read_at: string | null;
  created_at: string | null;
}

export interface StudentNotificationListResponse {
  notifications: StudentNotification[];
  unread_count: number;
}

/**
 * Maps a notification's related entity to a Student route — but ONLY for
 * routes that actually exist in this app. Anything not listed here (or a
 * notification with no related entity) renders as non-navigable. URLs are
 * built from a fixed prefix + an encoded id, never from free-form text.
 *
 * "APPLICATION" is a deliberate exception: `related_entity_id` is an
 * `applications.id`, not an opportunity id, so no fixed prefix can route
 * it directly — the generic list below is only the SAFE FALLBACK.
 * NotificationsView resolves it to the exact Job/Internship opportunity
 * (where Phase 1 now shows live status + interview details) via
 * `applicationOpportunityHref()` below, using data already available from
 * the student's own `listMyApplications()` — no backend change needed.
 * This also covers every INTERVIEW_SCHEDULED/rescheduled/cancelled
 * notification, which the producer writes as this same entity type (see
 * notification_producer.emit_interview_change).
 */
export function relatedHref(n: StudentNotification): string | null {
  const id = n.related_entity_id;
  if (!n.related_entity_type || !id) return null;
  switch (n.related_entity_type) {
    case "APPLICATION":
      // /student/applications has no per-id route — link to the list.
      // (NotificationsView upgrades this to the exact opportunity when it can.)
      return "/student/applications";
    case "ASSESSMENT":
      return `/student/assessment/${encodeURIComponent(id)}`;
    case "LEARNING_RESOURCE":
      return `/student/learning/${encodeURIComponent(id)}`;
    case "EVENT":
      return `/student/events/${encodeURIComponent(id)}`;
    case "MENTORSHIP":
      // Industry Mentorship was removed; no student-facing route exists.
      return null;
    case "INTERNSHIP_WORKSPACE":
      return `/student/my-internships/${encodeURIComponent(id)}`;
    case "JOB_TRAINING_ENROLLMENT":
      // `id` is a job_training_enrollments.id -- the Student Job Training
      // detail route (app/student/job-training/[enrollmentId]/page.tsx).
      return `/student/job-training/${encodeURIComponent(id)}`;
    case "WORKSHOP":
      // `id` is an industry_workshops.id (migration 058).
      return `/student/workshops/${encodeURIComponent(id)}`;
    case "PROJECT":
      // `id` is an industry_projects.id (migration 058).
      return `/student/industry-projects/${encodeURIComponent(id)}`;
    case "TRAINING":
      // `id` is an industry_training.id (migration 060).
      return `/student/trainings/${encodeURIComponent(id)}`;
    case "PARTICIPATION_WORKSPACE":
      // `id` is a participation_workspaces.id (migration 066) -- the
      // Project/Training/Workshop workspace's own detail route.
      return `/student/participation/workspaces/${encodeURIComponent(id)}`;
    case "INTERVIEW":
      // The current producer never emits this related_entity_type --
      // application-status changes AND interview scheduling/reschedule/
      // cancellation events are both written as related_entity_type
      // "APPLICATION" (see notification_producer.emit_interview_change),
      // resolved to the exact opportunity by NotificationsView. Kept here
      // only because the DB schema still permits the value; never crashes
      // if it's ever written.
      return null;
    default:
      return null;
  }
}

/** The Job/Internship opportunity detail route for a given `source_type` +
 * opportunity id. Used by NotificationsView to resolve an "APPLICATION"
 * notification to the exact posting once it has looked up the
 * application's opportunity via listMyApplications(). Same route shape as
 * DETAIL_BASE in my-applications-view.tsx. */
export function opportunityHref(sourceType: "JOB" | "INTERNSHIP", opportunityId: string): string {
  const base = sourceType === "JOB" ? "/student/jobs" : "/student/internships";
  return `${base}/${encodeURIComponent(opportunityId)}`;
}
