import { api } from "@/lib/api";
import type { InstitutionOverview } from "@/types/institution-analytics";

/**
 * Talks to the Institution dashboard overview API
 * (backend/app/api/institution.py, GET /api/v1/institution/overview).
 *
 * ONE call returns every dashboard metric, aggregated server-side and
 * scoped to the authenticated Institution account's linked students —
 * same architecture as lib/industry/analytics.ts's getIndustryAnalytics.
 * The frontend never re-aggregates or re-scopes what it renders.
 */
export function getInstitutionOverview(): Promise<InstitutionOverview> {
  return api.get("/api/v1/institution/overview");
}
