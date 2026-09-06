import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getInstitutionInternships: vi.fn(),
  getInstitutionInternshipOverview: vi.fn(),
  getAvailableInternships: vi.fn(),
  selectInstitutionInternship: vi.fn(),
  removeInstitutionInternship: vi.fn(),
}));

vi.mock("@/lib/institution/internships", () => ({
  getInstitutionInternships: mocks.getInstitutionInternships,
  getInstitutionInternshipOverview: mocks.getInstitutionInternshipOverview,
  getAvailableInternships: mocks.getAvailableInternships,
  selectInstitutionInternship: mocks.selectInstitutionInternship,
  removeInstitutionInternship: mocks.removeInstitutionInternship,
}));

import { InstitutionInternshipsView } from "@/components/institution/internships/internships-view";
import { ApiError } from "@/lib/api";
import type {
  AvailableInternshipListResponse,
  InstitutionInternshipListResponse,
  InstitutionInternshipOverviewResponse,
} from "@/types/institution-internship";

function list(overrides: Partial<InstitutionInternshipListResponse> = {}): InstitutionInternshipListResponse {
  return {
    internships: [
      {
        id: "i1",
        title: "Backend Intern",
        company_name: "Acme Corp",
        industry_id: "co-1",
        work_mode: "REMOTE",
        duration_months: 3,
        stipend_amount: 10000,
        stipend_currency: "INR",
        application_deadline: "2026-12-01",
        start_date: "2026-01-01",
        status: "PUBLISHED",
        association_id: "assoc-1",
        association_status: "ACTIVE",
        added_at: "2026-01-01T00:00:00Z",
        applicants_from_institution: 4,
        selected_from_institution: 1,
      },
    ],
    mode_options: ["REMOTE", "ONSITE"],
    status_options: ["PUBLISHED", "CLOSED"],
    ...overrides,
  };
}

function overview(
  overrides: Partial<InstitutionInternshipOverviewResponse> = {},
): InstitutionInternshipOverviewResponse {
  return {
    kpis: {
      curated_internships: 3,
      active_internships: 2,
      companies: 1,
      applicants: 10,
      selected_students: 4,
      active_participants: 2,
      completed_internships: 1,
      participation_unknown: 0,
    },
    departments: [
      {
        id: "d1",
        name: "CSE",
        student_count: 20,
        participants: 8,
        participation_rate: 40,
        selected_count: 4,
        completed_count: 1,
      },
      {
        id: "d2",
        name: "ECE",
        student_count: 0,
        participants: 0,
        participation_rate: null,
        selected_count: 0,
        completed_count: 0,
      },
    ],
    companies: [{ company_name: "Acme Corp", opportunities: 2, applicants: 10, selected: 4, completed: 1 }],
    mode_distribution: [{ mode: "REMOTE", count: 2 }],
    status_distribution: [{ status: "PUBLISHED", count: 2 }],
    application_status_distribution: [{ status: "SELECTED", count: 4 }],
    stipend: {
      available: true,
      note: "Stipend note",
      by_currency: [{ currency: "INR", internship_count: 2, average_stipend: 10000, min_stipend: 5000, max_stipend: 15000 }],
    },
    tenancy_note: "Tenancy note",
    eligibility_note: "Eligibility note",
    participation_note: "Participation note",
    curation_note: "Curation note",
    ...overrides,
  };
}

function available(
  overrides: Partial<AvailableInternshipListResponse> = {},
): AvailableInternshipListResponse {
  return {
    internships: [
      {
        id: "i2",
        title: "Design Intern",
        company_name: "Globex",
        industry_id: "co-2",
        work_mode: "ONSITE",
        duration_months: 6,
        stipend_amount: null,
        stipend_currency: "INR",
        application_deadline: null,
        start_date: null,
        status: "PUBLISHED",
      },
    ],
    mode_options: ["ONSITE"],
    ...overrides,
  };
}

describe("InstitutionInternshipsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches curated internships and overview once on mount, not available internships", () => {
    mocks.getInstitutionInternships.mockReturnValue(new Promise(() => {}));
    mocks.getInstitutionInternshipOverview.mockReturnValue(new Promise(() => {}));
    render(<InstitutionInternshipsView />);
    expect(mocks.getInstitutionInternships).toHaveBeenCalledTimes(1);
    expect(mocks.getInstitutionInternshipOverview).toHaveBeenCalledTimes(1);
    expect(mocks.getAvailableInternships).not.toHaveBeenCalled();
  });

  it("shows a loading state", () => {
    mocks.getInstitutionInternships.mockReturnValue(new Promise(() => {}));
    mocks.getInstitutionInternshipOverview.mockReturnValue(new Promise(() => {}));
    render(<InstitutionInternshipsView />);
    expect(screen.getByText(/Loading internships/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getInstitutionInternships.mockRejectedValueOnce(new ApiError(500, "boom"));
    mocks.getInstitutionInternshipOverview.mockResolvedValueOnce(overview());
    render(<InstitutionInternshipsView />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders KPIs, the curated table and breakdown sections by default", async () => {
    mocks.getInstitutionInternships.mockResolvedValueOnce(list());
    mocks.getInstitutionInternshipOverview.mockResolvedValueOnce(overview());
    render(<InstitutionInternshipsView />);

    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText("Selected Internships")).toBeInTheDocument();
    expect(screen.getByText("Internship Participation by Department")).toBeInTheDocument();
    expect(screen.getByText("Companies Offering Internships")).toBeInTheDocument();
    expect(screen.getByText("Internship Mode")).toBeInTheDocument();
  });

  it("shows an empty state when nothing is curated yet", async () => {
    mocks.getInstitutionInternships.mockResolvedValueOnce(list({ internships: [], mode_options: [], status_options: [] }));
    mocks.getInstitutionInternshipOverview.mockResolvedValueOnce(
      overview({
        kpis: {
          curated_internships: 0,
          active_internships: 0,
          companies: 0,
          applicants: 0,
          selected_students: 0,
          active_participants: 0,
          completed_internships: 0,
          participation_unknown: 0,
        },
      }),
    );
    render(<InstitutionInternshipsView />);
    expect(await screen.findByText("No internships selected yet")).toBeInTheDocument();
  });

  it("links to the student directory filtered to internship-selected students", async () => {
    mocks.getInstitutionInternships.mockResolvedValueOnce(list());
    mocks.getInstitutionInternshipOverview.mockResolvedValueOnce(overview());
    render(<InstitutionInternshipsView />);
    const link = await screen.findByText(/view selected students/i);
    expect(link.closest("a")).toHaveAttribute("href", "/institution/students?internship_status=SELECTED");
  });

  it("surfaces the curation, tenancy, eligibility and participation notes", async () => {
    mocks.getInstitutionInternships.mockResolvedValueOnce(list());
    mocks.getInstitutionInternshipOverview.mockResolvedValueOnce(overview());
    render(<InstitutionInternshipsView />);
    expect(await screen.findByText("Curation note")).toBeInTheDocument();
    expect(screen.getByText("Tenancy note")).toBeInTheDocument();
    expect(screen.getByText("Eligibility note")).toBeInTheDocument();
    expect(screen.getByText("Participation note")).toBeInTheDocument();
  });

  it("lazily loads available internships only when that tab is opened", async () => {
    mocks.getInstitutionInternships.mockResolvedValueOnce(list());
    mocks.getInstitutionInternshipOverview.mockResolvedValueOnce(overview());
    mocks.getAvailableInternships.mockReturnValue(new Promise(() => {}));
    render(<InstitutionInternshipsView />);
    await screen.findByText("Backend Intern");
    expect(mocks.getAvailableInternships).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole("tab", { name: /browse available internships/i }));
    expect(mocks.getAvailableInternships).toHaveBeenCalledTimes(1);
  });

  it("renders available internships with an Add to Institution action", async () => {
    mocks.getInstitutionInternships.mockResolvedValueOnce(list());
    mocks.getInstitutionInternshipOverview.mockResolvedValueOnce(overview());
    mocks.getAvailableInternships.mockResolvedValueOnce(available());
    render(<InstitutionInternshipsView />);
    await screen.findByText("Backend Intern");

    fireEvent.click(screen.getByRole("tab", { name: /browse available internships/i }));
    expect(await screen.findByText("Design Intern")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add to institution/i })).toBeInTheDocument();
  });

  it("adding an available internship calls select and reloads the curated list", async () => {
    mocks.getInstitutionInternships.mockResolvedValueOnce(list());
    mocks.getInstitutionInternshipOverview.mockResolvedValueOnce(overview());
    mocks.getAvailableInternships.mockResolvedValueOnce(available());
    mocks.selectInstitutionInternship.mockResolvedValueOnce({
      id: "assoc-2", internship_id: "i2", status: "ACTIVE", created_at: null, updated_at: null,
    });
    mocks.getInstitutionInternships.mockResolvedValueOnce(list());
    mocks.getInstitutionInternshipOverview.mockResolvedValueOnce(overview());
    render(<InstitutionInternshipsView />);
    await screen.findByText("Backend Intern");

    fireEvent.click(screen.getByRole("tab", { name: /browse available internships/i }));
    await screen.findByText("Design Intern");
    fireEvent.click(screen.getByRole("button", { name: /add to institution/i }));

    await vi.waitFor(() => expect(mocks.selectInstitutionInternship).toHaveBeenCalledWith("i2"));
    await vi.waitFor(() => expect(mocks.getInstitutionInternships).toHaveBeenCalledTimes(2));
  });

  it("removing a curated internship calls remove and reloads the curated list", async () => {
    mocks.getInstitutionInternships.mockResolvedValueOnce(list());
    mocks.getInstitutionInternshipOverview.mockResolvedValueOnce(overview());
    mocks.removeInstitutionInternship.mockResolvedValueOnce({
      id: "assoc-1", internship_id: "i1", status: "INACTIVE", created_at: null, updated_at: null,
    });
    mocks.getInstitutionInternships.mockResolvedValueOnce(list({ internships: [] }));
    mocks.getInstitutionInternshipOverview.mockResolvedValueOnce(overview());
    render(<InstitutionInternshipsView />);
    await screen.findByText("Backend Intern");

    fireEvent.click(screen.getByRole("button", { name: /remove backend intern from your institution/i }));

    await vi.waitFor(() => expect(mocks.removeInstitutionInternship).toHaveBeenCalledWith("i1"));
    await vi.waitFor(() => expect(mocks.getInstitutionInternships).toHaveBeenCalledTimes(2));
  });
});
