import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ getInstitutionOverview: vi.fn() }));

vi.mock("@/lib/institution/dashboard", () => ({ getInstitutionOverview: mocks.getInstitutionOverview }));

import { InstitutionDashboardView } from "@/components/institution/dashboard/institution-dashboard-view";
import { ApiError } from "@/lib/api";
import type { InstitutionOverview } from "@/types/institution-analytics";

function overview(overrides: Partial<InstitutionOverview> = {}): InstitutionOverview {
  return {
    generated_at: "2026-09-04T00:00:00Z",
    institution_name: "Test Institute of Technology",
    student_metrics: {
      total_linked_students: 100,
      placed: 40,
      unplaced_active: 35,
      not_participating: 25,
      placement_percentage: 40,
    },
    department_metrics: [
      { department: "CSE", department_id: "dept-cse", total_students: 60, placed_students: 30, placement_percentage: 50 },
      { department: "ECE", department_id: "dept-ece", total_students: 40, placed_students: 10, placement_percentage: 25 },
    ],
    opportunities: {
      active_jobs: 5,
      active_internships: 3,
      recent: [
        {
          id: "job-1",
          title: "Backend Engineer",
          opportunity_type: "JOB",
          company_name: "Acme Corp",
          posted_at: "2026-09-01T00:00:00Z",
          applicants_from_your_institution: 4,
        },
      ],
      platform_wide: true,
    },
    industry: { total_industry_partners: 12, recent_postings_count: 3, platform_wide: true },
    collaborations: { pending: 2, active: 1, total: 5 },
    upcoming_events: [
      {
        id: "ws-1",
        title: "AI in Practice",
        event_type: "WORKSHOP",
        start_date: "2026-10-01",
        organizer: "Acme Corp",
        platform_wide: true,
      },
    ],
    student_insights: {
      students_with_no_applications: 25,
      students_actively_applying: 35,
      top_skills: [{ skill_name: "Python", student_count: 42 }],
      assessments_completed: 10,
      average_assessment_percentage: 72.5,
    },
    tenancy_note: "Only linked students are counted.",
    eligibility_note: "Eligible students is not shown.",
    ...overrides,
  };
}

describe("InstitutionDashboardView", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches the overview once on mount", () => {
    mocks.getInstitutionOverview.mockReturnValue(new Promise(() => {}));
    render(<InstitutionDashboardView />);
    expect(mocks.getInstitutionOverview).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getInstitutionOverview.mockReturnValue(new Promise(() => {}));
    render(<InstitutionDashboardView />);
    expect(screen.getByText(/Loading dashboard/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getInstitutionOverview.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<InstitutionDashboardView />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders KPIs, placement overview, departments, opportunities and events from the API data", async () => {
    mocks.getInstitutionOverview.mockResolvedValueOnce(overview());
    render(<InstitutionDashboardView />);

    expect((await screen.findAllByText("Students")).length).toBeGreaterThan(0);
    expect(screen.getByText("100")).toBeInTheDocument(); // total linked students KPI
    expect(screen.getByText("Placement Overview")).toBeInTheDocument();
    expect(screen.getByText("Department Performance")).toBeInTheDocument();
    expect(screen.getByText("CSE")).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("AI in Practice")).toBeInTheDocument();
  });

  it("surfaces the tenancy and eligibility notes", async () => {
    mocks.getInstitutionOverview.mockResolvedValueOnce(overview());
    render(<InstitutionDashboardView />);
    expect(await screen.findByText(/Only linked students are counted/i)).toBeInTheDocument();
    expect(screen.getByText(/Eligible students is not shown/i)).toBeInTheDocument();
  });

  it("renders an empty state for an institution with no linked students or activity", async () => {
    mocks.getInstitutionOverview.mockResolvedValueOnce(
      overview({
        student_metrics: {
          total_linked_students: 0,
          placed: 0,
          unplaced_active: 0,
          not_participating: 0,
          placement_percentage: null,
        },
        department_metrics: [],
        opportunities: { active_jobs: 0, active_internships: 0, recent: [], platform_wide: true },
        collaborations: { pending: 0, active: 0, total: 0 },
        upcoming_events: [],
      }),
    );
    render(<InstitutionDashboardView />);
    expect(await screen.findByText("Nothing to show yet")).toBeInTheDocument();
  });

  it("never renders a fabricated eligible-students figure", async () => {
    mocks.getInstitutionOverview.mockResolvedValueOnce(overview());
    render(<InstitutionDashboardView />);
    await screen.findAllByText("Students");
    expect(screen.queryByText(/eligible students?:/i)).not.toBeInTheDocument();
  });
});
