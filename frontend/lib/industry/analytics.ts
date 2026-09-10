import { api } from "@/lib/api";
import type { IndustryAnalytics } from "@/types/analytics";

/**
 * Talks to the Industry analytics API
 * (backend/app/api/analytics.py, GET /api/v1/analytics/industry).
 *
 * ONE call returns every dashboard metric, aggregated server-side and
 * scoped to the authenticated Industry account. The frontend never sends
 * an industry id and never re-aggregates — it renders what the backend
 * computed. This replaces the dashboard-style fan-out of ~9 parallel
 * browser requests.
 */
export function getIndustryAnalytics(): Promise<IndustryAnalytics> {
  return api.get("/api/v1/analytics/industry");
}
