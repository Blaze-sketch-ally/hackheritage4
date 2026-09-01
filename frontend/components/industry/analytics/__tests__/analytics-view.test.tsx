import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ getIndustryAnalytics: vi.fn() }));

vi.mock("@/lib/industry/analytics", () => ({ getIndustryAnalytics: mocks.getIndustryAnalytics }));

import { AnalyticsView } from "@/components/industry/analytics/analytics-view";
import { ApiError } from "@/lib/api";
import type { IndustryAnalytics } from "@/types/analytics";

function analytics(overrides: Partial<IndustryAnalytics> = {}): IndustryAnalytics {
  return {
    generated_at: "2026-09-02T00:00:00Z",
    kpis: {
      opportunities_total: 12,
      opportunities_published: 7,
      applications_total: 40,
      shortlisted: 6,
      interviews_total: 3,
      interviews_upcoming: 2,
      selected: 2,
      collaborations_total: 5,
      collaborations_active: 1,
    },
    funnel_counts: {
      APPLIED: 20,
      UNDER_REVIEW: 5,
      SHORTLISTED: 6,
      INTERVIEW_SCHEDULED: 4,
      SELECTED: 2,
      REJECTED: 3,
      WITHDRAWN: 0,
    },
    funnel_total: 40,
    application_status_distribution: [
      { status: "APPLIED", count: 20 },
      { status: "SHORTLISTED", count: 6 },
      { status: "SELECTED", count: 2 },
    ],
    opportunity_breakdown: [
      { opportunity_type: "INTERNSHIP", total: 5, published: 3 },
      { opportunity_type: "JOB", total: 7, published: 4 },
    ],
    interview_metrics: { total: 3, scheduled: 2, completed: 1, cancelled: 0, upcoming: 2 },
    top_opportunities: [
      { id: "job-1", title: "Backend Engineer", opportunity_type: "JOB", application_count: 18 },
    ],
    timeline: [
      { period: "2026-04", opportunities_created: 1, applications_received: 2 },
      { period: "2026-05", opportunities_created: 0, applications_received: 5 },
      { period: "2026-06", opportunities_created: 2, applications_received: 8 },
      { period: "2026-07", opportunities_created: 1, applications_received: 10 },
      { period: "2026-08", opportunities_created: 3, applications_received: 9 },
      { period: "2026-09", opportunities_created: 4, applications_received: 6 },
    ],
    historical_note:
      "Time-series reflects when records were created. The database stores only current status, not when it changed.",
    interviews_available: true,
    ...overrides,
  };
}

describe("AnalyticsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches analytics once on mount", () => {
    mocks.getIndustryAnalytics.mockReturnValue(new Promise(() => {}));
    render(<AnalyticsView />);
    expect(mocks.getIndustryAnalytics).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getIndustryAnalytics.mockReturnValue(new Promise(() => {}));
    render(<AnalyticsView />);
    expect(screen.getByText(/Loading analytics/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getIndustryAnalytics.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<AnalyticsView />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders KPI cards, funnel, breakdown and status distribution from the API data", async () => {
    mocks.getIndustryAnalytics.mockResolvedValueOnce(analytics());
    render(<AnalyticsView />);

    expect(await screen.findByText("Applications")).toBeInTheDocument();
    expect(screen.getByText("40")).toBeInTheDocument(); // applications total KPI
    expect(screen.getByText("Recruitment funnel")).toBeInTheDocument();
    expect(screen.getByText("Opportunity breakdown")).toBeInTheDocument();
    expect(screen.getByText("Application status distribution")).toBeInTheDocument();
    expect(screen.getByText("Top opportunities by applications")).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
  });

  it("shows every metric with a definition and surfaces the historical caveat", async () => {
    mocks.getIndustryAnalytics.mockResolvedValueOnce(analytics());
    render(<AnalyticsView />);
    expect(
      await screen.findByText(/database stores only current status, not when it changed/i),
    ).toBeInTheDocument();
  });

  it("renders an empty state for an account with no data", async () => {
    mocks.getIndustryAnalytics.mockResolvedValueOnce(
      analytics({
        kpis: {
          opportunities_total: 0,
          opportunities_published: 0,
          applications_total: 0,
          shortlisted: 0,
          interviews_total: 0,
          interviews_upcoming: 0,
          selected: 0,
          collaborations_total: 0,
          collaborations_active: 0,
        },
      }),
    );
    render(<AnalyticsView />);
    expect(await screen.findByText("Nothing to analyse yet")).toBeInTheDocument();
  });

  it("degrades interview panel when interview scheduling is unavailable", async () => {
    mocks.getIndustryAnalytics.mockResolvedValueOnce(analytics({ interviews_available: false }));
    render(<AnalyticsView />);
    expect(
      await screen.findByText(/Interview scheduling has not been enabled/i),
    ).toBeInTheDocument();
  });
});
