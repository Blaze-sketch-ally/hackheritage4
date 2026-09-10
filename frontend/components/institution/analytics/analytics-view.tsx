"use client";

import { useEffect, useState } from "react";
import {
  BarChart3,
  Briefcase,
  ClipboardCheck,
  GraduationCap,
  Info,
  TrendingUp,
  Users,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/dashboard/stat-card";
import { Loading } from "@/components/common/loading";
import { ErrorState } from "@/components/common/error-state";
import { EmptyState } from "@/components/common/empty-state";
import { BarList } from "@/components/industry/analytics/bar-list";
import { ApiError } from "@/lib/api";
import { getInstitutionAnalytics } from "@/lib/institution/analytics";
import type { AnalyticsFilterOptions, InstitutionAnalyticsReport } from "@/types/institution-analytics-report";
import { ANALYTICS_METRIC_DEFINITIONS, APPLICATION_STATUS_LABELS } from "@/types/institution-analytics-report";
import { AnalyticsFilters, type AnalyticsFilterState } from "@/components/institution/analytics/analytics-filters";
import { DepartmentAnalyticsTable } from "@/components/institution/analytics/department-analytics-table";
import { PlacementDrivesAnalytics } from "@/components/institution/analytics/placement-drives-analytics";
import { CompanyHiringTable } from "@/components/institution/analytics/company-hiring-table";
import { SkillGapTable } from "@/components/institution/analytics/skill-gap-table";
import { AnalyticsTrendChart } from "@/components/institution/analytics/analytics-trend-chart";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; report: InstitutionAnalyticsReport };

function Section({
  title,
  definition,
  children,
}: {
  title: string;
  definition: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
        <p className="flex items-start gap-1.5 text-xs text-muted-foreground">
          <Info className="mt-0.5 size-3 shrink-0" aria-hidden="true" />
          {definition}
        </p>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/**
 * The Institution Analytics workspace (Phase 6): deep analytical view,
 * distinct from the concise operational Dashboard. One server-side
 * aggregation call per filter change -- same architecture as
 * InstitutionDashboardView / AnalyticsView (Industry).
 */
export function InstitutionAnalyticsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [filters, setFilters] = useState<AnalyticsFilterState>({ departmentId: null, batch: null });
  const [filterOptions, setFilterOptions] = useState<AnalyticsFilterOptions | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getInstitutionAnalytics({ department_id: filters.departmentId, batch: filters.batch })
      .then((report) => {
        if (cancelled) return;
        setState({ status: "ready", report });
        setFilterOptions(report.filter_options);
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load analytics."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [filters.departmentId, filters.batch, reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  function handleFiltersChange(next: AnalyticsFilterState) {
    setFilters(next);
    setState({ status: "loading" });
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Institution Analytics</h1>
        <p className="text-sm text-muted-foreground">
          A deeper analytical workspace on top of the Dashboard -- students, placements, departments, companies,
          skills and more, computed live from your own linked students&apos; records.
        </p>
      </div>

      {filterOptions ? (
        <AnalyticsFilters options={filterOptions} value={filters} onChange={handleFiltersChange} />
      ) : null}

      {state.status === "loading" ? <Loading label="Loading analytics…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={
            state.error.status === 401 ? "Your session has expired. Please sign in again." : state.error.message
          }
          onRetry={state.error.status !== 401 ? reload : undefined}
        />
      ) : null}

      {state.status === "ready" ? <Ready report={state.report} /> : null}
    </div>
  );
}

function Ready({ report }: { report: InstitutionAnalyticsReport }) {
  const { overview } = report;
  const nothingYet =
    overview.total_students === 0 &&
    report.placements.total_drives === 0 &&
    report.companies.length === 0;

  if (nothingYet) {
    return (
      <EmptyState
        icon={BarChart3}
        title="Nothing to analyse yet"
        description="Once students are linked to your institution and placement activity picks up, your analytics will appear here."
      />
    );
  }

  const statusDistribution = report.applications.status_distribution
    .filter((s) => s.count > 0)
    .map((s) => ({ key: s.status, label: APPLICATION_STATUS_LABELS[s.status] ?? s.status, value: s.count }));

  const internshipStatusDistribution = report.internships.status_distribution
    .filter((s) => s.count > 0)
    .map((s) => ({ key: s.status, label: APPLICATION_STATUS_LABELS[s.status] ?? s.status, value: s.count }));

  const skillBars = report.skills.top_skills.map((s) => ({
    key: s.skill_name,
    label: s.skill_name,
    value: s.student_count,
    hint: s.coverage_percentage != null ? `${s.coverage_percentage}%` : undefined,
  }));

  return (
    <div className="space-y-6">
      {/* Core KPIs (Part 6) */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-4">
        <StatCard label="Total Students" value={overview.total_students.toLocaleString()} icon={Users} accent="indigo" />
        <StatCard
          label="Placed"
          value={overview.placed_students.toLocaleString()}
          helperText={`of ${overview.total_students}`}
          icon={GraduationCap}
          accent="emerald"
        />
        <StatCard label="Unplaced" value={overview.unplaced_students.toLocaleString()} icon={Users} accent="amber" />
        <StatCard
          label="Placement Rate"
          value={overview.placement_rate != null ? `${overview.placement_rate}%` : "N/A"}
          icon={TrendingUp}
          accent="violet"
        />
        <StatCard
          label="With Applications"
          value={overview.students_with_applications.toLocaleString()}
          icon={ClipboardCheck}
          accent="blue"
        />
        <StatCard
          label="Without Applications"
          value={overview.students_without_applications.toLocaleString()}
          icon={Users}
          accent="amber"
        />
        <StatCard
          label="Internship Participants"
          value={overview.internship_participants.toLocaleString()}
          icon={Briefcase}
          accent="blue"
        />
        <StatCard
          label="Active / Completed Drives"
          value={`${overview.active_placement_drives} / ${overview.completed_placement_drives}`}
          icon={Briefcase}
          accent="indigo"
        />
      </div>

      <DepartmentAnalyticsTable departments={report.departments} />

      <PlacementDrivesAnalytics placements={report.placements} />

      <CompanyHiringTable companies={report.companies} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Application Status Distribution" definition={ANALYTICS_METRIC_DEFINITIONS.applications}>
          <BarList data={statusDistribution} emptyText="No applications yet." />
          <p className="mt-3 text-xs text-muted-foreground">
            {report.applications.total_applications} total ·{" "}
            {report.applications.applications_per_applying_student != null
              ? `${report.applications.applications_per_applying_student} per applying student`
              : "—"}
          </p>
        </Section>

        <Section title="Top Skills" definition={ANALYTICS_METRIC_DEFINITIONS.skills}>
          <BarList data={skillBars} emptyText="No skills on file yet." accentClass="bg-sky-500/70" />
        </Section>
      </div>

      <SkillGapTable skillGaps={report.skill_gaps} />

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Internships" definition={ANALYTICS_METRIC_DEFINITIONS.internships}>
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
            {[
              ["Participants", report.internships.participants],
              ["Applications", report.internships.applications_total],
              [
                "Participation",
                report.internships.participation_rate != null ? `${report.internships.participation_rate}%` : "N/A",
              ],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded-lg bg-muted/50 px-3 py-2">
                <p className="text-xl font-semibold tabular-nums">{value}</p>
                <p className="text-[11px] text-muted-foreground">{label}</p>
              </div>
            ))}
          </div>
          <div className="mt-3">
            <BarList data={internshipStatusDistribution} emptyText="No internship applications yet." accentClass="bg-emerald-500/70" />
          </div>
        </Section>

        <Section title="Assessments" definition={ANALYTICS_METRIC_DEFINITIONS.assessments}>
          <div className="grid grid-cols-3 gap-3">
            {[
              ["Assessed", report.assessments.students_assessed],
              ["Attempts", report.assessments.total_attempts],
              [
                "Avg. Score",
                report.assessments.average_score != null ? `${report.assessments.average_score}%` : "—",
              ],
            ].map(([label, value]) => (
              <div key={label as string} className="rounded-lg bg-muted/50 px-3 py-2">
                <p className="text-xl font-semibold tabular-nums">{value}</p>
                <p className="text-[11px] text-muted-foreground">{label}</p>
              </div>
            ))}
          </div>
        </Section>
      </div>

      <Section title="Interviews" definition={ANALYTICS_METRIC_DEFINITIONS.interviews}>
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {[
            ["Total", report.interviews.total],
            ["Students", report.interviews.students_interviewed],
            ["Scheduled", report.interviews.scheduled],
            ["Completed", report.interviews.completed],
            ["Upcoming", report.interviews.upcoming],
          ].map(([label, value]) => (
            <div key={label as string} className="rounded-lg bg-muted/50 px-3 py-2">
              <p className="text-xl font-semibold tabular-nums">{value}</p>
              <p className="text-[11px] text-muted-foreground">{label}</p>
            </div>
          ))}
        </div>
      </Section>

      <Section title="Monthly Trend" definition={ANALYTICS_METRIC_DEFINITIONS.trends}>
        <AnalyticsTrendChart trends={report.trends} />
      </Section>

      <div className="space-y-2">
        {[report.tenancy_note, report.eligibility_note, report.filter_scope_note].map((note) => (
          <p
            key={note}
            className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground"
          >
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            {note}
          </p>
        ))}
      </div>
    </div>
  );
}
