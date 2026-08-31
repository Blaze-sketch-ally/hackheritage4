import { api } from "@/lib/api";
import type { Portfolio } from "@/types/portfolio";

/**
 * The industry-facing portfolio read (Phase 1N) -- one endpoint,
 * scoped by application, not by student. See
 * backend/app/api/applications.py's GET /applications/{id}/portfolio
 * for the full authorization chain: the application must exist, belong
 * to an opportunity owned by the caller, and the returned portfolio
 * belongs to that application's student -- all proven server-side (RLS
 * first, defense-in-depth checks second), never trusted from the
 * frontend.
 */
export function getApplicationPortfolio(applicationId: string): Promise<Portfolio> {
  return api.get(`/api/v1/applications/${applicationId}/portfolio`);
}
