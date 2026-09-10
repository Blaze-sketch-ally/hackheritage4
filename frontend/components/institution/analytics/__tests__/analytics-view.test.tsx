import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ getInstitutionAnalytics: vi.fn() }));

vi.mock("@/lib/institution/analytics", () => ({ getInstitutionAnalytics: mocks.getInstitutionAnalytics }));

import { InstitutionAnalyticsView } from "@/components/institution/analytics/analytics-view";
import { ApiError } from "@/lib/api";
import type { InstitutionAnalyticsReport } from "@/types/institution-analytics-report";

function report(overrides: Partial<InstitutionAnalyticsReport> = {}): InstitutionAnalyticsReport {
  return {
    generated_at: "2026-09-04T00:00:00Z",
    institution_name: "Test Institute of Technology",
    filters_applied: { department_id: null, batch: null, date_from: null, date_to: null },
    filter_options: {
      departments: [{ id: "dept-cse", name: "CSE" }],
      batches: [2026, 2027],
    },
    overview: {
      total_students: 100,
      placed_students: 40,
      unplaced_students: 35,
      placement_rate: 40,
      students_with_applications: 75,
      students_without_applications: 25,
      internship_participants: 12,
      active_placement_drives: 2,
      completed_placement_drives: 1,
    },
    departments: [
      {
        id: "dept-cse",
        name: "CSE",
        code: "CSE",
        is_active: true,
        student_count: 60,
        placed_count: 30,
        unplaced_count: 20,
        no_applications_count: 10,
        placement_rate: 50,
        internship_selected_count: 4,
      },
      {
        id: "dept-empty",
        name: "Mechanical",
        code: "ME",
        is_active: true,
        student_count: 0,
        placed_count: 0,
        unplaced_count: 0,
        no_applications_count: 0,
        placement_rate: null,
        internship_selected_count: 0,
      },
    ],
    placements: {
      total_drives: 1,
      active_drives: 1,
      completed_drives: 0,
      cancelled_drives: 0,
      draft_drives: 0,
      participating_students: 10,
      placed_students: 3,
      total_selected_offers: 3,
      placement_rate: 30,
      average_applicants_per_drive: 10,
      department_breakdown: [{ department: "CSE", placed_count: 3 }],
      drives: [
        {
          id: "drive-1",
          title: "Campus Drive 2026",
          company_name: "Acme Corp",
          status: "OPEN",
          eligible_count: 40,
          applied_count: 0,
          selected_count: 0,
          selection_rate: null,
        },
      ],
    },
    companies: [
      { company_name: "Acme Corp", postings_count: 2, applicants: 10, selected_offers: 3, unique_students_placed: 2 },
    ],
    applications: {
      total_applications: 80,
      students_with_applications: 75,
      students_without_applications: 25,
      applications_per_applying_student: 1.1,
      status_distribution: [
        { status: "APPLIED", count: 30 },
        { status: "SELECTED", count: 10 },
      ],
    },
    skills: {
      total_students_considered: 100,
      top_skills: [{ skill_name: "Python", student_count: 42, coverage_percentage: 42 }],
    },
    skill_gaps: { available: true, note: "Threshold note", items: [
      { skill_name: "Kubernetes", student_coverage_count: 2, student_coverage_percentage: 2, job_demand_count: 5, high_demand: true, low_coverage: true },
    ] },
    internships: {
      available: true,
      note: "note",
      participants: 12,
      applications_total: 15,
      participation_rate: 12,
      status_distribution: [{ status: "SELECTED", count: 4 }],
    },
    assessments: { students_assessed: 20, total_attempts: 25, average_score: 72.5 },
    interviews: { total: 5, students_interviewed: 4, scheduled: 2, completed: 2, cancelled: 1, upcoming: 1 },
    trends: {
      has_sufficient_data: true,
      months: [{ period: "2026-09", applications: 10, selections: 2, internship_applications: 3 }],
      historical_note: "Historical note",
    },
    tenancy_note: "Tenancy note",
    eligibility_note: "Eligibility note",
    filter_scope_note: "Filter scope note",
    ...overrides,
  };
}

describe("InstitutionAnalyticsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches analytics once on mount", () => {
    mocks.getInstitutionAnalytics.mockReturnValue(new Promise(() => {}));
    render(<InstitutionAnalyticsView />);
    expect(mocks.getInstitutionAnalytics).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getInstitutionAnalytics.mockReturnValue(new Promise(() => {}));
    render(<InstitutionAnalyticsView />);
    expect(screen.getByText(/Loading analytics/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getInstitutionAnalytics.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<InstitutionAnalyticsView />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders KPI cards and section tables from the API data", async () => {
    mocks.getInstitutionAnalytics.mockResolvedValueOnce(report());
    render(<InstitutionAnalyticsView />);

    expect(await screen.findByText("Total Students")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("Department Performance")).toBeInTheDocument();
    expect(screen.getByText("Placement Drives")).toBeInTheDocument();
    expect(screen.getByText("Companies Hiring Your Students")).toBeInTheDocument();
    expect(screen.getByText("Skill Gaps")).toBeInTheDocument();
    expect(screen.getAllByText("Acme Corp").length).toBeGreaterThan(0);
  });

  it("shows N/A for a drive's selection rate when it has zero applicants", async () => {
    mocks.getInstitutionAnalytics.mockResolvedValueOnce(report());
    render(<InstitutionAnalyticsView />);
    expect(await screen.findByText("Campus Drive 2026")).toBeInTheDocument();
    expect(screen.getAllByText("N/A").length).toBeGreaterThan(0);
  });

  it("shows N/A rather than a fabricated 0% for a department with zero students", async () => {
    mocks.getInstitutionAnalytics.mockResolvedValueOnce(report());
    render(<InstitutionAnalyticsView />);
    expect(await screen.findByText("Mechanical")).toBeInTheDocument();
    const naCells = screen.getAllByText("N/A");
    expect(naCells.length).toBeGreaterThan(0);
  });

  it("shows the skill-gap unavailable empty state honestly instead of a fabricated result", async () => {
    mocks.getInstitutionAnalytics.mockResolvedValueOnce(
      report({ skill_gaps: { available: false, note: "unavailable note", items: [] } }),
    );
    render(<InstitutionAnalyticsView />);
    expect(await screen.findByText("Skill-demand comparison unavailable")).toBeInTheDocument();
  });

  it("renders an empty state for an institution with no data at all", async () => {
    mocks.getInstitutionAnalytics.mockResolvedValueOnce(
      report({
        overview: {
          total_students: 0,
          placed_students: 0,
          unplaced_students: 0,
          placement_rate: null,
          students_with_applications: 0,
          students_without_applications: 0,
          internship_participants: 0,
          active_placement_drives: 0,
          completed_placement_drives: 0,
        },
        departments: [],
        placements: {
          total_drives: 0,
          active_drives: 0,
          completed_drives: 0,
          cancelled_drives: 0,
          draft_drives: 0,
          participating_students: 0,
          placed_students: 0,
          total_selected_offers: 0,
          placement_rate: null,
          average_applicants_per_drive: null,
          department_breakdown: [],
          drives: [],
        },
        companies: [],
      }),
    );
    render(<InstitutionAnalyticsView />);
    expect(await screen.findByText("Nothing to analyse yet")).toBeInTheDocument();
  });

  it("shows Not enough historical data yet when trends have insufficient data", async () => {
    mocks.getInstitutionAnalytics.mockResolvedValueOnce(
      report({ trends: { has_sufficient_data: false, months: [], historical_note: "note" } }),
    );
    render(<InstitutionAnalyticsView />);
    expect(await screen.findByText("Not enough historical data yet.")).toBeInTheDocument();
  });

  it("renders department and batch filter controls populated from filter_options", async () => {
    mocks.getInstitutionAnalytics.mockResolvedValueOnce(report());
    render(<InstitutionAnalyticsView />);
    await screen.findByText("Total Students");

    expect(screen.getByRole("combobox", { name: /filter by department/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /filter by batch/i })).toBeInTheDocument();
  });

  it("surfaces the tenancy, eligibility and filter-scope notes", async () => {
    mocks.getInstitutionAnalytics.mockResolvedValueOnce(report());
    render(<InstitutionAnalyticsView />);
    expect(await screen.findByText("Tenancy note")).toBeInTheDocument();
    expect(screen.getByText("Eligibility note")).toBeInTheDocument();
    expect(screen.getByText("Filter scope note")).toBeInTheDocument();
  });
});
