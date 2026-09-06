import { api } from "@/lib/api";
import type { InstitutionAnalyticsReport } from "@/types/institution-analytics-report";

export interface AnalyticsQuery {
  department_id?: string | null;
  batch?: number | null;
  date_from?: string | null;
  date_to?: string | null;
}

/**
 * Talks to the Institution Analytics workspace API
 * (backend/app/api/institution.py, GET /api/v1/institution/analytics).
 *
 * ONE call returns every analytics section, aggregated server-side --
 * same "one call, server does the aggregation" architecture as
 * lib/institution/dashboard.ts's getInstitutionOverview and
 * lib/industry/analytics.ts's getIndustryAnalytics. The frontend never
 * re-aggregates or re-scopes what it renders; it only forwards the
 * active filters as query params.
 */
export function getInstitutionAnalytics(query: AnalyticsQuery = {}): Promise<InstitutionAnalyticsReport> {
  const params = new URLSearchParams();
  if (query.department_id) params.set("department_id", query.department_id);
  if (query.batch != null) params.set("batch", String(query.batch));
  if (query.date_from) params.set("date_from", query.date_from);
  if (query.date_to) params.set("date_to", query.date_to);
  const qs = params.toString();
  return api.get(`/api/v1/institution/analytics${qs ? `?${qs}` : ""}`);
}
