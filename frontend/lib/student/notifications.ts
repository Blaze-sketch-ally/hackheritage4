import { api } from "@/lib/api";
import type {
  StudentNotification,
  StudentNotificationListResponse,
} from "@/types/student-notification";

/**
 * Talks to OUR Student Notifications API
 * (backend/app/api/student_notifications.py, /api/v1/student/notifications).
 * The only place the frontend builds these requests -- components call
 * these functions, never `api.*` directly.
 *
 * Every call goes through lib/api.ts's apiFetch(), which attaches the
 * student's own Supabase access token. No `student_id` / `recipient_id`
 * is ever sent -- the backend derives the recipient from the token
 * (require_student -> current_user.id).
 *
 * There is NO create function: notifications are written only by trusted
 * system-context code. The only writes here toggle the caller's own read
 * state, and they send an EMPTY body -- the path identifies the
 * notification, the token identifies the recipient.
 */

export function listNotifications(params?: {
  unread?: boolean;
  limit?: number;
}): Promise<StudentNotificationListResponse> {
  const query = new URLSearchParams();
  if (params?.unread) query.set("unread", "true");
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return api.get(`/api/v1/student/notifications${qs ? `?${qs}` : ""}`);
}

export function getNotification(notificationId: string): Promise<StudentNotification> {
  return api.get(`/api/v1/student/notifications/${encodeURIComponent(notificationId)}`);
}

export function markNotificationRead(notificationId: string): Promise<StudentNotification> {
  return api.patch(
    `/api/v1/student/notifications/${encodeURIComponent(notificationId)}/read`,
  );
}

export function markNotificationUnread(notificationId: string): Promise<StudentNotification> {
  return api.patch(
    `/api/v1/student/notifications/${encodeURIComponent(notificationId)}/unread`,
  );
}

export function markAllNotificationsRead(): Promise<{ updated: number }> {
  return api.post("/api/v1/student/notifications/read-all");
}
