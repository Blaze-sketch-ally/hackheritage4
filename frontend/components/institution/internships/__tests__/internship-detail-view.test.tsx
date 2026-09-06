import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getInstitutionInternship: vi.fn(),
  removeInstitutionInternship: vi.fn(),
}));

vi.mock("@/lib/institution/internships", () => ({
  getInstitutionInternship: mocks.getInstitutionInternship,
  removeInstitutionInternship: mocks.removeInstitutionInternship,
}));

import { InstitutionInternshipDetailView } from "@/components/institution/internships/internship-detail-view";
import { ApiError } from "@/lib/api";
import type { InstitutionInternshipDetail } from "@/types/institution-internship";

function detail(overrides: Partial<InstitutionInternshipDetail> = {}): InstitutionInternshipDetail {
  return {
    id: "i1",
    title: "Backend Intern",
    description: "Build APIs.",
    company_name: "Acme Corp",
    industry_id: "co-1",
    location: "Remote",
    work_mode: "REMOTE",
    duration_months: 3,
    stipend_amount: 10000,
    stipend_currency: "INR",
    eligibility_criteria: "CGPA 7+",
    application_deadline: "2026-12-01",
    start_date: "2026-01-01",
    status: "PUBLISHED",
    association_id: "assoc-1",
    association_status: "ACTIVE",
    added_at: "2026-01-01T00:00:00Z",
    applicants_from_institution: 1,
    selected_from_institution: 1,
    participation: { not_started: 0, active: 1, completed: 0, unknown: 0 },
    status_distribution: [
      { status: "SELECTED", count: 1 },
      { status: "APPLIED", count: 0 },
    ],
    applicants: [
      {
        application_id: "a1",
        student_id: "s1",
        full_name: "Ada Lovelace",
        username: "ada",
        department: "CSE",
        cgpa: 9.1,
        status: "SELECTED",
        applied_at: "2026-01-01T00:00:00Z",
        participation_estimate: "ACTIVE",
        interview: null,
      },
    ],
    eligibility_note: "Eligibility note",
    participation_note: "Participation note",
    privacy_note: "Privacy note",
    ...overrides,
  };
}

describe("InstitutionInternshipDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches the internship once on mount", () => {
    mocks.getInstitutionInternship.mockReturnValue(new Promise(() => {}));
    render(<InstitutionInternshipDetailView internshipId="i1" />);
    expect(mocks.getInstitutionInternship).toHaveBeenCalledWith("i1");
  });

  it("shows a loading state", () => {
    mocks.getInstitutionInternship.mockReturnValue(new Promise(() => {}));
    render(<InstitutionInternshipDetailView internshipId="i1" />);
    expect(screen.getByText(/Loading internship/i)).toBeInTheDocument();
  });

  it("shows a not-curated message on 404", async () => {
    mocks.getInstitutionInternship.mockRejectedValueOnce(new ApiError(404, "Internship not found."));
    render(<InstitutionInternshipDetailView internshipId="i1" />);
    expect(await screen.findByText(/isn't part of your institution's curated list/i)).toBeInTheDocument();
  });

  it("renders overview, participation and applicants", async () => {
    mocks.getInstitutionInternship.mockResolvedValueOnce(detail());
    render(<InstitutionInternshipDetailView internshipId="i1" />);

    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Build APIs.")).toBeInTheDocument();
    expect(screen.getByText("Ada Lovelace")).toBeInTheDocument();
    expect(screen.getByText("CGPA 7+")).toBeInTheDocument();
  });

  it("never shows a private interview note or student contact info", async () => {
    mocks.getInstitutionInternship.mockResolvedValueOnce(detail());
    render(<InstitutionInternshipDetailView internshipId="i1" />);
    await screen.findByText("Backend Intern");
    expect(screen.queryByText(/@/)).not.toBeInTheDocument();
    expect(screen.getByText("Privacy note")).toBeInTheDocument();
  });

  it("shows an unknown-participation caveat instead of guessing", async () => {
    mocks.getInstitutionInternship.mockResolvedValueOnce(
      detail({
        participation: { not_started: 0, active: 0, completed: 0, unknown: 1 },
        applicants: [
          {
            application_id: "a1",
            student_id: "s1",
            full_name: "Ada Lovelace",
            username: "ada",
            department: "CSE",
            cgpa: 9.1,
            status: "SELECTED",
            applied_at: "2026-01-01T00:00:00Z",
            participation_estimate: "UNKNOWN",
            interview: null,
          },
        ],
      }),
    );
    render(<InstitutionInternshipDetailView internshipId="i1" />);
    expect(await screen.findByText(/unknown participation stage/i)).toBeInTheDocument();
  });

  it("shows a Remove from Institution action for an actively curated internship", async () => {
    mocks.getInstitutionInternship.mockResolvedValueOnce(detail());
    render(<InstitutionInternshipDetailView internshipId="i1" />);
    await screen.findByText("Backend Intern");
    expect(screen.getByRole("button", { name: /remove from institution/i })).toBeInTheDocument();
  });

  it("hides the Remove action and shows a Removed badge once removed", async () => {
    mocks.getInstitutionInternship.mockResolvedValueOnce(detail({ association_status: "INACTIVE" }));
    render(<InstitutionInternshipDetailView internshipId="i1" />);
    await screen.findByText("Backend Intern");
    expect(screen.queryByRole("button", { name: /remove from institution/i })).not.toBeInTheDocument();
    expect(screen.getByText("Removed")).toBeInTheDocument();
  });

  it("clicking Remove calls the remove endpoint and reloads", async () => {
    mocks.getInstitutionInternship.mockResolvedValueOnce(detail());
    mocks.removeInstitutionInternship.mockResolvedValueOnce({
      id: "assoc-1", internship_id: "i1", status: "INACTIVE", created_at: null, updated_at: null,
    });
    mocks.getInstitutionInternship.mockResolvedValueOnce(detail({ association_status: "INACTIVE" }));
    render(<InstitutionInternshipDetailView internshipId="i1" />);
    await screen.findByText("Backend Intern");

    fireEvent.click(screen.getByRole("button", { name: /remove from institution/i }));

    await vi.waitFor(() => expect(mocks.removeInstitutionInternship).toHaveBeenCalledWith("i1"));
    expect(await screen.findByText("Removed")).toBeInTheDocument();
  });
});
