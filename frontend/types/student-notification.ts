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
 */
export function relatedHref(n: StudentNotification): string | null {
  const id = n.related_entity_id;
  if (!n.related_entity_type || !id) return null;
  switch (n.related_entity_type) {
    case "APPLICATION":
      // /student/applications has no per-id route — link to the list.
      return "/student/applications";
    case "ASSESSMENT":
      return `/student/assessment/${encodeURIComponent(id)}`;
    case "LEARNING_RESOURCE":
      return `/student/learning/${encodeURIComponent(id)}`;
    case "EVENT":
      return `/student/events/${encodeURIComponent(id)}`;
    case "MENTORSHIP":
      return `/student/mentorship/${encodeURIComponent(id)}`;
    case "INTERNSHIP_WORKSPACE":
      return `/student/my-internships/${encodeURIComponent(id)}`;
    case "INTERVIEW":
      // No student-facing interview route exists yet.
      return null;
    default:
      return null;
  }
}
