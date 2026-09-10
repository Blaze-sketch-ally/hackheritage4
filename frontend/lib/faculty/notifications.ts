import { api } from "@/lib/api";
import type {
  FacultyNotification,
  FacultyNotificationListResponse,
} from "@/types/faculty-notification";

/**
 * Talks to OUR Faculty Notifications API
 * (backend/app/api/faculty_notifications.py, /api/v1/faculty/notifications).
 * The only place the frontend builds these requests -- components call
 * these functions, never `api.*` directly. Mirrors lib/student/notifications.ts.
 *
 * Every call goes through lib/api.ts's apiFetch(), which attaches the
 * Faculty member's own Supabase access token. No `faculty_id` /
 * `recipient_id` is ever sent -- the backend derives the recipient from
 * the token (require_faculty -> current_user.id).
 *
 * There is NO create function: notifications are written only by trusted
 * system-context code. The only writes here toggle the caller's own read
 * state, and they send an EMPTY body -- the path identifies the
 * notification, the token identifies the recipient.
 */

export function listNotifications(params?: {
  unread?: boolean;
  limit?: number;
}): Promise<FacultyNotificationListResponse> {
  const query = new URLSearchParams();
  if (params?.unread) query.set("unread", "true");
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return api.get(`/api/v1/faculty/notifications${qs ? `?${qs}` : ""}`);
}

export function getUnreadCount(): Promise<{ unread_count: number }> {
  return api.get("/api/v1/faculty/notifications/unread-count");
}

export function getNotification(notificationId: string): Promise<FacultyNotification> {
  return api.get(`/api/v1/faculty/notifications/${encodeURIComponent(notificationId)}`);
}

export function markNotificationRead(notificationId: string): Promise<FacultyNotification> {
  return api.patch(
    `/api/v1/faculty/notifications/${encodeURIComponent(notificationId)}/read`,
  );
}

export function markNotificationUnread(notificationId: string): Promise<FacultyNotification> {
  return api.patch(
    `/api/v1/faculty/notifications/${encodeURIComponent(notificationId)}/unread`,
  );
}

export function markAllNotificationsRead(): Promise<{ updated: number }> {
  return api.post("/api/v1/faculty/notifications/read-all");
}
