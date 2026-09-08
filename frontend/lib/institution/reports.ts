import { api } from "@/lib/api";
import type { InstitutionReportResponse, ReportType } from "@/types/institution-reports";

export interface ReportQuery {
  report_type: ReportType;
  department_id?: string | null;
  batch?: number | null;
  company_id?: string | null;
  status?: string | null;
  event_type?: string | null;
  collaboration_status?: string | null;
  date_from?: string | null;
  date_to?: string | null;
  page?: number;
  page_size?: number;
}

/** Talks to backend/app/api/institution.py, GET /api/v1/institution/reports.
 * One call returns the complete dataset for the selected report -- the
 * frontend never re-aggregates or fetches per-row. */
export function getInstitutionReport(query: ReportQuery): Promise<InstitutionReportResponse> {
  const params = new URLSearchParams();
  params.set("report_type", query.report_type);
  if (query.department_id) params.set("department_id", query.department_id);
  if (query.batch != null) params.set("batch", String(query.batch));
  if (query.company_id) params.set("company_id", query.company_id);
  if (query.status) params.set("status", query.status);
  if (query.event_type) params.set("event_type", query.event_type);
  if (query.collaboration_status) params.set("collaboration_status", query.collaboration_status);
  if (query.date_from) params.set("date_from", query.date_from);
  if (query.date_to) params.set("date_to", query.date_to);
  if (query.page) params.set("page", String(query.page));
  if (query.page_size) params.set("page_size", String(query.page_size));
  return api.get(`/api/v1/institution/reports?${params.toString()}`);
}
