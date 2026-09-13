// Mirrors backend/app/schemas/industry_notification.py and
// database/migrations/055_industry_notifications.sql. Keep in sync.
//
// Notifications are produced by trusted system-context code (there is no
// insert policy on the table). The frontend only lists them, marks them
// read/unread, and reads the unread count. It never creates one.

export const NOTIFICATION_TYPES = ["NEW_APPLICATION", "WITHDRAWAL", "SYSTEM"] as const;
export type NotificationType = (typeof NOTIFICATION_TYPES)[number];

export const RELATED_ENTITY_TYPES = [
  "INTERNSHIP_APPLICATION",
  "JOB_APPLICATION",
  "PROJECT_APPLICATION",
  "WORKSHOP_APPLICATION",
  "TRAINING_APPLICATION",
] as const;
export type RelatedEntityType = (typeof RELATED_ENTITY_TYPES)[number];

export interface IndustryNotification {
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

export interface IndustryNotificationListResponse {
  notifications: IndustryNotification[];
  unread_count: number;
}

/**
 * Maps a notification's related entity to an Industry route. For
 * INTERNSHIP_APPLICATION/JOB_APPLICATION, `related_entity_id` is the
 * application id (Industry already has a per-application detail route).
 * For PROJECT_APPLICATION/WORKSHOP_APPLICATION it is the POSTING id --
 * the destination is that posting's Applicants view, not a specific
 * applicant (see backend/app/services/notification_producer.py).
 */
export function relatedHref(n: IndustryNotification): string | null {
  const id = n.related_entity_id;
  if (!n.related_entity_type || !id) return null;
  switch (n.related_entity_type) {
    case "INTERNSHIP_APPLICATION":
    case "JOB_APPLICATION":
      return `/industry/applicants/${encodeURIComponent(id)}`;
    case "PROJECT_APPLICATION":
      return `/industry/projects/${encodeURIComponent(id)}/applicants`;
    case "WORKSHOP_APPLICATION":
      return `/industry/workshops/${encodeURIComponent(id)}/applicants`;
    case "TRAINING_APPLICATION":
      return `/industry/training/${encodeURIComponent(id)}/applicants`;
    default:
      return null;
  }
}
