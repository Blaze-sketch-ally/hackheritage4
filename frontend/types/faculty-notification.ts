// Mirrors backend/app/schemas/faculty_notification.py and
// database/migrations/066_faculty_notifications.sql. Keep in sync.
//
// Notifications are produced by trusted system-context code (there is no
// insert policy on the table). The frontend only lists them, marks them
// read/unread, and reads the unread count. It never creates one.

export const NOTIFICATION_TYPES = [
  "EVALUATION_ASSIGNED",
  "EVALUATION_REVOKED",
  "REVIEW_DECISION",
  "MENTORSHIP",
] as const;
export type NotificationType = (typeof NOTIFICATION_TYPES)[number];

export const RELATED_ENTITY_TYPES = ["QUESTION", "EVALUATION", "MENTORSHIP"] as const;
export type RelatedEntityType = (typeof RELATED_ENTITY_TYPES)[number];

export interface FacultyNotification {
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

export interface FacultyNotificationListResponse {
  notifications: FacultyNotification[];
  unread_count: number;
}

/**
 * Maps a notification's related entity to a Faculty route -- but ONLY
 * for routes that actually exist in this app. Anything not listed here
 * (or a notification with no related entity) renders as non-navigable.
 * URLs are built from a fixed prefix + an encoded id, never from
 * free-form text.
 */
export function relatedHref(n: FacultyNotification): string | null {
  const id = n.related_entity_id;
  if (!n.related_entity_type || !id) return null;
  switch (n.related_entity_type) {
    case "QUESTION":
      return `/faculty/questions/${encodeURIComponent(id)}`;
    case "EVALUATION":
      return `/faculty/evaluation-workspace/${encodeURIComponent(id)}`;
    case "MENTORSHIP":
      // /faculty/mentorship has no per-id route -- link to the list.
      return "/faculty/mentorship";
    default:
      return null;
  }
}
