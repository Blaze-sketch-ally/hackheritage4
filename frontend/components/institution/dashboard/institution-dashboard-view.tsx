"use client";

import { useEffect, useState } from "react";
import { Info, LayoutDashboard } from "lucide-react";
import { Loading } from "@/components/common/loading";
import { ErrorState } from "@/components/common/error-state";
import { EmptyState } from "@/components/common/empty-state";
import { ApiError } from "@/lib/api";
import { getInstitutionOverview } from "@/lib/institution/dashboard";
import type { InstitutionOverview } from "@/types/institution-analytics";
import { InstitutionKpis } from "@/components/institution/dashboard/institution-kpis";
import { PlacementOverview } from "@/components/institution/dashboard/placement-overview";
import { DepartmentPerformance } from "@/components/institution/dashboard/department-performance";
import { OpportunitiesOverview } from "@/components/institution/dashboard/opportunities-overview";
import { IndustryOverview } from "@/components/institution/dashboard/industry-overview";
import { UpcomingEvents } from "@/components/institution/dashboard/upcoming-events";
import { StudentInsights } from "@/components/institution/dashboard/student-insights";
import { PlacementDrivesLink } from "@/components/institution/dashboard/placement-drives-link";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; overview: InstitutionOverview };

/**
 * Single server-side aggregation call (GET /api/v1/institution/overview),
 * one page-level loading/error/ready state — same architecture as
 * components/industry/analytics/analytics-view.tsx, not the older
 * multi-fetch dashboard fan-out pattern.
 */
export function InstitutionDashboardView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getInstitutionOverview()
      .then((overview) => {
        if (!cancelled) setState({ status: "ready", overview });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load the dashboard."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Institution Dashboard</h1>
        <p className="text-sm text-muted-foreground">
          Overview of students, placements, opportunities and industry engagement.
        </p>
      </div>

      {state.status === "loading" ? <Loading label="Loading dashboard…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={
            state.error.status === 401
              ? "Your session has expired. Please sign in again."
              : state.error.message
          }
          onRetry={state.error.status !== 401 ? reload : undefined}
        />
      ) : null}

      {state.status === "ready" ? <Ready overview={state.overview} /> : null}
    </div>
  );
}

function Ready({ overview }: { overview: InstitutionOverview }) {
  const hasNothing =
    overview.student_metrics.total_linked_students === 0 &&
    overview.opportunities.recent.length === 0 &&
    overview.collaborations.total === 0 &&
    overview.upcoming_events.length === 0;

  return (
    <div className="space-y-6">
      <InstitutionKpis overview={overview} />

      <PlacementDrivesLink />

      {hasNothing ? (
        <EmptyState
          icon={LayoutDashboard}
          title="Nothing to show yet"
          description="Once students are linked to your institution and industry activity picks up, your dashboard will populate here."
        />
      ) : null}

      <div className="grid gap-6 lg:grid-cols-2">
        <PlacementOverview metrics={overview.student_metrics} />
        <StudentInsights insights={overview.student_insights} />
      </div>

      <DepartmentPerformance departments={overview.department_metrics} />

      <div className="grid gap-6 lg:grid-cols-2">
        <OpportunitiesOverview opportunities={overview.opportunities} />
        <IndustryOverview industry={overview.industry} collaborations={overview.collaborations} />
      </div>

      <UpcomingEvents events={overview.upcoming_events} />

      <div className="space-y-2">
        <p className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {overview.tenancy_note}
        </p>
        <p className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
          <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
          {overview.eligibility_note}
        </p>
      </div>
    </div>
  );
}
