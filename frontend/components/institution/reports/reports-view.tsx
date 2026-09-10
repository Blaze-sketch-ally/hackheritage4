"use client";

import { useState } from "react";
import { Download, FileText, Printer } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Loading } from "@/components/common/loading";
import { ErrorState } from "@/components/common/error-state";
import { EmptyState } from "@/components/common/empty-state";
import { ApiError } from "@/lib/api";
import { getInstitutionReport } from "@/lib/institution/reports";
import { downloadCsv } from "@/lib/csv-export";
import type { InstitutionReportResponse, ReportType } from "@/types/institution-reports";
import { REPORT_TYPE_DESCRIPTIONS, REPORT_TYPE_LABELS, REPORT_TYPES } from "@/types/institution-reports";
import { EMPTY_FILTERS, ReportFilters, type ReportFilterState } from "@/components/institution/reports/report-filters";
import { ReportOutput } from "@/components/institution/reports/report-output";
import { reportToCsv } from "@/components/institution/reports/report-csv";

type LoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; report: InstitutionReportResponse };

function formatFilterSummary(report: InstitutionReportResponse): string {
  const f = report.filters_applied;
  const parts: string[] = [];
  if (f.department_id) parts.push("Department filter applied");
  if (f.batch) parts.push(`Batch: ${f.batch}`);
  if (f.company_id) parts.push("Company filter applied");
  if (f.status) parts.push(`Status: ${f.status}`);
  if (f.event_type) parts.push(`Event type: ${f.event_type}`);
  if (f.collaboration_status) parts.push(`Collaboration status: ${f.collaboration_status}`);
  if (f.date_from || f.date_to) parts.push(`Date range: ${f.date_from ?? "…"} to ${f.date_to ?? "…"}`);
  return parts.length > 0 ? parts.join(" · ") : "No filters applied";
}

/**
 * Institution Reports (Phase 11): a predefined report catalog, not a
 * report-builder. Selecting a report and clicking Generate makes ONE
 * call to GET /api/v1/institution/reports -- the backend returns the
 * complete dataset for that report, reusing the same definitions as
 * Analytics/Placements/Internships/Students/Departments/Industry
 * Partners/Events/Collaborations (see institution_reports_service's own
 * docstring). Export is CSV only (client-side, no dependency) plus a
 * browser Print -- no PDF library exists anywhere in this project.
 */
export function InstitutionReportsView() {
  const [reportType, setReportType] = useState<ReportType>("PLACEMENT");
  const [filters, setFilters] = useState<ReportFilterState>(EMPTY_FILTERS);
  const [state, setState] = useState<LoadState>({ status: "idle" });

  function selectReport(next: ReportType) {
    setReportType(next);
    setFilters(EMPTY_FILTERS);
    setState({ status: "idle" });
  }

  async function generate() {
    setState({ status: "loading" });
    try {
      const report = await getInstitutionReport({
        report_type: reportType,
        department_id: filters.departmentId,
        batch: filters.batch,
        company_id: filters.companyId,
        status: filters.status,
        event_type: filters.eventType,
        collaboration_status: filters.collaborationStatus,
        date_from: filters.dateFrom,
        date_to: filters.dateTo,
      });
      setState({ status: "ready", report });
    } catch (err) {
      setState({
        status: "error",
        error: err instanceof ApiError ? err : new ApiError(0, "Could not generate this report."),
      });
    }
  }

  function exportCsv() {
    if (state.status !== "ready") return;
    const csv = reportToCsv(state.report);
    if (!csv) return;
    downloadCsv(`${state.report.report_type.toLowerCase()}-report`, csv);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6 print:max-w-none">
      <div className="print:hidden">
        <h1 className="text-xl font-semibold">Reports</h1>
        <p className="text-sm text-muted-foreground">
          Formal, filterable reports built from your institution&apos;s existing data -- not a second Analytics
          page.
        </p>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4 print:hidden">
        {REPORT_TYPES.map((type) => (
          <button key={type} type="button" onClick={() => selectReport(type)} className="text-left">
            <Card className={reportType === type ? "ring-2 ring-indigo-500" : undefined}>
              <CardContent className="space-y-1 py-4">
                <p className="text-sm font-semibold">{REPORT_TYPE_LABELS[type]}</p>
                <p className="text-xs text-muted-foreground">{REPORT_TYPE_DESCRIPTIONS[type]}</p>
              </CardContent>
            </Card>
          </button>
        ))}
      </div>

      <Card className="print:hidden">
        <CardContent className="space-y-4 py-4">
          <ReportFilters reportType={reportType} value={filters} onChange={setFilters} />
          <Button onClick={generate} disabled={state.status === "loading"}>
            <FileText className="size-4" /> {state.status === "loading" ? "Generating…" : "Generate Report"}
          </Button>
        </CardContent>
      </Card>

      {state.status === "idle" ? (
        <EmptyState icon={FileText} title="No report generated yet" description="Choose a report and filters above, then click Generate Report." />
      ) : null}

      {state.status === "loading" ? <Loading label="Generating report…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={state.error.status === 401 ? "Your session has expired. Please sign in again." : state.error.message}
          onRetry={state.error.status !== 401 ? generate : undefined}
        />
      ) : null}

      {state.status === "ready" ? (
        <div className="space-y-6">
          <div className="flex flex-col gap-2 border-b pb-4 sm:flex-row sm:items-start sm:justify-between">
            <div>
              <h2 className="text-lg font-semibold">{REPORT_TYPE_LABELS[state.report.report_type]}</h2>
              <p className="text-sm text-muted-foreground">Institution: {state.report.institution_name ?? "—"}</p>
              <p className="text-xs text-muted-foreground">Filters: {formatFilterSummary(state.report)}</p>
              <p className="text-xs text-muted-foreground">
                Generated {new Date(state.report.generated_at).toLocaleString()}
              </p>
            </div>
            <div className="flex gap-2 print:hidden">
              <Button variant="outline" size="sm" onClick={exportCsv}>
                <Download className="size-4" /> Export CSV
              </Button>
              <Button variant="outline" size="sm" onClick={() => window.print()}>
                <Printer className="size-4" /> Print
              </Button>
            </div>
          </div>

          <ReportOutput report={state.report} />
        </div>
      ) : null}
    </div>
  );
}
