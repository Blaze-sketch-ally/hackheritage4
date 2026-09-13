import { api } from "@/lib/api";
import type {
  IndustryNotification,
  IndustryNotificationListResponse,
} from "@/types/industry-notification";

/**
 * Talks to OUR Industry Notifications API
 * (backend/app/api/industry_notifications.py, /api/v1/industry/notifications).
 * The only place the frontend builds these requests -- components call
 * these functions, never `api.*` directly.
 *
 * Every call goes through lib/api.ts's apiFetch(), which attaches the
 * industry account's own Supabase access token. No `industry_id` is ever
 * sent -- the backend derives the recipient from the token
 * (require_industry -> current_user.id).
 *
 * There is NO create function: notifications are written only by trusted
 * system-context code. The only writes here toggle the caller's own read
 * state, and they send an EMPTY body.
 */

export function listNotifications(params?: {
  unread?: boolean;
  limit?: number;
}): Promise<IndustryNotificationListResponse> {
  const query = new URLSearchParams();
  if (params?.unread) query.set("unread", "true");
  if (params?.limit) query.set("limit", String(params.limit));
  const qs = query.toString();
  return api.get(`/api/v1/industry/notifications${qs ? `?${qs}` : ""}`);
}

export function getNotification(notificationId: string): Promise<IndustryNotification> {
  return api.get(`/api/v1/industry/notifications/${encodeURIComponent(notificationId)}`);
}

export function markNotificationRead(notificationId: string): Promise<IndustryNotification> {
  return api.patch(
    `/api/v1/industry/notifications/${encodeURIComponent(notificationId)}/read`,
  );
}

export function markNotificationUnread(notificationId: string): Promise<IndustryNotification> {
  return api.patch(
    `/api/v1/industry/notifications/${encodeURIComponent(notificationId)}/unread`,
  );
}

export function markAllNotificationsRead(): Promise<{ updated: number }> {
  return api.post("/api/v1/industry/notifications/read-all");
}
