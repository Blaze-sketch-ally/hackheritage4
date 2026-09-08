import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getInstitutionReport: vi.fn(),
}));

vi.mock("@/lib/institution/reports", () => ({
  getInstitutionReport: mocks.getInstitutionReport,
}));

vi.mock("@/lib/institution/departments", () => ({
  getInstitutionDepartments: vi.fn().mockResolvedValue({ departments: [] }),
}));

vi.mock("@/lib/institution/industry-partners", () => ({
  searchIndustryPartnerCompanies: vi.fn().mockResolvedValue({ companies: [] }),
}));

import { InstitutionReportsView } from "@/components/institution/reports/reports-view";
import { ApiError } from "@/lib/api";
import type { InstitutionReportResponse } from "@/types/institution-reports";

function placementReport(overrides: Partial<InstitutionReportResponse> = {}): InstitutionReportResponse {
  return {
    report_type: "PLACEMENT",
    institution_name: "Test Institute",
    generated_at: "2026-01-01T00:00:00Z",
    filters_applied: {
      department_id: null,
      batch: null,
      company_id: null,
      status: null,
      event_type: null,
      collaboration_status: null,
      date_from: null,
      date_to: null,
    },
    placement: {
      summary: {
        total_students: 100,
        students_with_applications: 60,
        students_selected: 25,
        placement_rate: 25,
        companies_involved: 4,
        active_placement_drives: 2,
      },
      department_breakdown: [
        { department_id: "d1", department: "CSE", student_count: 50, placed_count: 20, placement_rate: 40 },
      ],
      company_breakdown: [
        { company_name: "Acme Corp", applicants: 10, selected_offers: 4, unique_students_placed: 3, selection_rate: 40 },
      ],
      status_breakdown: [
        { label: "APPLIED", count: 30 },
        { label: "SELECTED", count: 25 },
      ],
      note: "Filter scope note",
    },
    ...overrides,
  };
}

describe("InstitutionReportsView", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows the report catalog and an idle empty state before generating", () => {
    render(<InstitutionReportsView />);
    expect(screen.getByText("Placement Report")).toBeInTheDocument();
    expect(screen.getByText("Internship Report")).toBeInTheDocument();
    expect(screen.getByText("Student Report")).toBeInTheDocument();
    expect(screen.getByText("Department Report")).toBeInTheDocument();
    expect(screen.getByText("Industry / Company Report")).toBeInTheDocument();
    expect(screen.getByText("Events Report")).toBeInTheDocument();
    expect(screen.getByText("Collaboration Report")).toBeInTheDocument();
    expect(screen.getByText("No report generated yet")).toBeInTheDocument();
  });

  it("does not fetch anything until Generate Report is clicked", () => {
    render(<InstitutionReportsView />);
    expect(mocks.getInstitutionReport).not.toHaveBeenCalled();
  });

  it("shows a loading state while generating", async () => {
    mocks.getInstitutionReport.mockReturnValue(new Promise(() => {}));
    render(<InstitutionReportsView />);
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));
    expect(await screen.findByText(/Generating report/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getInstitutionReport.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<InstitutionReportsView />);
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("generates the default (Placement) report and renders its summary and tables", async () => {
    mocks.getInstitutionReport.mockResolvedValueOnce(placementReport());
    render(<InstitutionReportsView />);
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));

    expect(await screen.findByText("Institution: Test Institute")).toBeInTheDocument();
    expect(screen.getByText("Total Students")).toBeInTheDocument();
    expect(screen.getByText("100")).toBeInTheDocument();
    expect(screen.getByText("CSE")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Filter scope note")).toBeInTheDocument();
  });

  it("switches report type and resets filters/state when a different catalog card is clicked", async () => {
    mocks.getInstitutionReport.mockResolvedValueOnce(placementReport());
    render(<InstitutionReportsView />);
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));
    await screen.findByText("Institution: Test Institute");

    fireEvent.click(screen.getByText("Events Report"));
    expect(screen.getByText("No report generated yet")).toBeInTheDocument();
    expect(mocks.getInstitutionReport).toHaveBeenCalledTimes(1);
  });

  it("forwards the selected report_type to the API call", async () => {
    mocks.getInstitutionReport.mockResolvedValue(
      placementReport({
        report_type: "COLLABORATION",
        placement: undefined,
        collaboration: { collaborations: [], status_breakdown: [], note: "note" },
      }),
    );
    render(<InstitutionReportsView />);
    fireEvent.click(screen.getByText("Collaboration Report"));
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));

    await screen.findByText("Institution: Test Institute");
    expect(mocks.getInstitutionReport).toHaveBeenCalledWith(expect.objectContaining({ report_type: "COLLABORATION" }));
  });

  it("shows an empty-result message when a filter produces no rows", async () => {
    mocks.getInstitutionReport.mockResolvedValueOnce(
      placementReport({
        placement: {
          summary: {
            total_students: 0,
            students_with_applications: 0,
            students_selected: 0,
            placement_rate: null,
            companies_involved: 0,
            active_placement_drives: 0,
          },
          department_breakdown: [],
          company_breakdown: [],
          status_breakdown: [],
          note: "Filter scope note",
        },
      }),
    );
    render(<InstitutionReportsView />);
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));
    await screen.findByText("Institution: Test Institute");
    expect(screen.getByText("No company activity.")).toBeInTheDocument();
  });

  it("shows the Export CSV and Print actions once a report is ready", async () => {
    mocks.getInstitutionReport.mockResolvedValueOnce(placementReport());
    render(<InstitutionReportsView />);
    fireEvent.click(screen.getByRole("button", { name: /generate report/i }));
    await screen.findByText("Institution: Test Institute");
    expect(screen.getByRole("button", { name: /export csv/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /print/i })).toBeInTheDocument();
  });
});
