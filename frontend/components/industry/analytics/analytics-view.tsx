"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  BarChart3,
  CalendarClock,
  Info,
  RefreshCw,
  type LucideIcon,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/common/empty-state";
import { ApiError } from "@/lib/api";
import { getIndustryAnalytics } from "@/lib/industry/analytics";
import { APPLICATION_STATUS_LABELS, type ApplicationStatus } from "@/types/application";
import {
  METRIC_DEFINITIONS,
  OPPORTUNITY_TYPE_LABELS,
  type IndustryAnalytics,
} from "@/types/analytics";
import { RecruitmentFunnel } from "@/components/industry/recruitment-funnel";
import { BarList } from "@/components/industry/analytics/bar-list";
import { ActivityTimeline } from "@/components/industry/analytics/activity-timeline";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; analytics: IndustryAnalytics };

function Kpi({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string;
  value: number;
  hint: string;
  icon?: LucideIcon;
}) {
  return (
    <Card>
      <CardContent className="space-y-1 py-4">
        <div className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
          {Icon ? <Icon className="size-3.5" aria-hidden="true" /> : null}
          {label}
        </div>
        <p className="text-2xl font-semibold tabular-nums">{value}</p>
        <p className="text-[11px] leading-tight text-muted-foreground/70">{hint}</p>
      </CardContent>
    </Card>
  );
}

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

export function AnalyticsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getIndustryAnalytics()
      .then((analytics) => {
        if (!cancelled) setState({ status: "ready", analytics });
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
  }, [reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted-foreground">
          A live view of your recruitment, opportunities and collaborations. Every number is
          computed from your own records right now.
        </p>
      </div>

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading analytics…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {state.error.status === 401
                  ? "Your session has expired. Please sign in again."
                  : "Could not load analytics."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status !== 401 ? (
              <Button variant="outline" size="sm" onClick={reload}>
                <RefreshCw className="size-3.5" /> Try again
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? <Ready analytics={state.analytics} /> : null}
    </div>
  );
}

function Ready({ analytics }: { analytics: IndustryAnalytics }) {
  const { kpis } = analytics;
  const nothingYet =
    kpis.opportunities_total === 0 &&
    kpis.applications_total === 0 &&
    kpis.collaborations_total === 0;

  if (nothingYet) {
    return (
      <EmptyState
        icon={BarChart3}
        title="Nothing to analyse yet"
        description="Post an opportunity and start receiving applications — your metrics will appear here."
      />
    );
  }

  const statusDistribution = analytics.application_status_distribution
    .filter((s) => s.count > 0)
    .map((s) => ({
      key: s.status,
      label: APPLICATION_STATUS_LABELS[s.status as ApplicationStatus] ?? s.status,
      value: s.count,
    }));

  const breakdown = analytics.opportunity_breakdown.map((b) => ({
    key: b.opportunity_type,
    label: OPPORTUNITY_TYPE_LABELS[b.opportunity_type] ?? b.opportunity_type,
    value: b.total,
    hint: `${b.published} published`,
  }));

  const topOpportunities = analytics.top_opportunities.map((t) => ({
    key: t.id,
    label: t.title,
    value: t.application_count,
  }));

  return (
    <div className="space-y-6">
      {/* KPI cards */}
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
        <Kpi label="Opportunities" value={kpis.opportunities_total} hint={METRIC_DEFINITIONS.opportunities} />
        <Kpi label="Applications" value={kpis.applications_total} hint={METRIC_DEFINITIONS.applications} />
        <Kpi label="Shortlisted" value={kpis.shortlisted} hint={METRIC_DEFINITIONS.shortlisted} />
        <Kpi
          label="Interviews"
          value={kpis.interviews_total}
          hint={METRIC_DEFINITIONS.interviews}
          icon={CalendarClock}
        />
        <Kpi label="Selected" value={kpis.selected} hint={METRIC_DEFINITIONS.selected} />
        <Kpi
          label="Collaborations"
          value={kpis.collaborations_total}
          hint={METRIC_DEFINITIONS.collaborations}
        />
      </div>

      {/* Recruitment funnel (current snapshot) */}
      <Section title="Recruitment funnel" definition={METRIC_DEFINITIONS.funnel}>
        <RecruitmentFunnel
          summary={{ counts: analytics.funnel_counts, total: analytics.funnel_total }}
        />
      </Section>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Application status distribution" definition={METRIC_DEFINITIONS.statusDistribution}>
          <BarList data={statusDistribution} emptyText="No applications yet." />
        </Section>

        <Section title="Opportunity breakdown" definition={METRIC_DEFINITIONS.breakdown}>
          <BarList data={breakdown} emptyText="No opportunities posted yet." />
        </Section>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Section title="Interviews" definition={METRIC_DEFINITIONS.interviewMetrics}>
          {analytics.interviews_available ? (
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
              {[
                ["Total", analytics.interview_metrics.total],
                ["Upcoming", analytics.interview_metrics.upcoming],
                ["Completed", analytics.interview_metrics.completed],
                ["Cancelled", analytics.interview_metrics.cancelled],
              ].map(([label, value]) => (
                <div key={label as string} className="rounded-lg bg-muted/50 px-3 py-2">
                  <p className="text-xl font-semibold tabular-nums">{value as number}</p>
                  <p className="text-[11px] text-muted-foreground">{label}</p>
                </div>
              ))}
            </div>
          ) : (
            <p className="text-sm text-muted-foreground/70">
              Interview scheduling has not been enabled on this database yet.
            </p>
          )}
        </Section>

        <Section title="Top opportunities by applications" definition={METRIC_DEFINITIONS.topOpportunities}>
          <BarList data={topOpportunities} emptyText="No applications yet." accentClass="bg-sky-500/70" />
        </Section>
      </div>

      {/* Time-based (creation dates only) */}
      <Section title="Monthly activity" definition={METRIC_DEFINITIONS.timeline}>
        <ActivityTimeline timeline={analytics.timeline} />
      </Section>

      <p className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
        <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
        {analytics.historical_note}
      </p>
    </div>
  );
}
