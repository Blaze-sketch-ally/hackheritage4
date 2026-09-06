import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getMyInstitutionWorkspace: vi.fn(),
  getMyLinkRequests: vi.fn(),
  resolveInstitution: vi.fn(),
  createLinkRequest: vi.fn(),
  cancelLinkRequest: vi.fn(),
}));

vi.mock("@/lib/student/institution", () => ({
  getMyInstitutionWorkspace: mocks.getMyInstitutionWorkspace,
}));

vi.mock("@/lib/institution-links", () => ({
  getMyLinkRequests: mocks.getMyLinkRequests,
  resolveInstitution: mocks.resolveInstitution,
  createLinkRequest: mocks.createLinkRequest,
  cancelLinkRequest: mocks.cancelLinkRequest,
}));

import { MyInstitutionView } from "@/components/student/institution/my-institution-view";
import { ApiError } from "@/lib/api";
import type { StudentInstitutionResponse } from "@/types/student-institution";

function workspace(overrides: Partial<StudentInstitutionResponse> = {}): StudentInstitutionResponse {
  return {
    linked: true,
    institution: { id: "inst-1", institution_name: "ABC University", institution_type: "UNIVERSITY", location: "Delhi", website_url: null },
    profile: { department_id: "d1", department: "CSE", batch: 2026, cgpa: 8.5, verified_at: "2026-01-01T00:00:00Z" },
    kpis: { placement_drives: 1, internships: 1, events: 1, active_applications: 1 },
    placement_drives: [
      {
        id: "pd1", title: "Campus Drive 2026", description: null, status: "OPEN",
        application_deadline: "2026-12-01", drive_date: "2026-12-10", mode: "ONSITE", venue: "Auditorium",
        company_name: "Acme Corp", job_id: "j1", is_eligible: true, eligibility_reasons: [],
        already_applied: false, application_status: null,
      },
    ],
    internships: [
      {
        id: "i1", title: "Backend Intern", description: "Build APIs.", company_name: "Acme Corp",
        work_mode: "REMOTE", duration_months: 3, stipend_amount: 10000, stipend_currency: "INR",
        application_deadline: "2026-12-01", start_date: "2026-01-01", eligibility_criteria: null,
        already_applied: false, application_status: null,
      },
    ],
    events: [
      {
        id: "e1", title: "Kickoff Session", description: "Kickoff.", event_type: "PLACEMENT_ORIENTATION",
        mode: "ONSITE", venue: "Hall A", start_at: "2026-03-01T10:00:00Z", end_at: null,
        company_name: null, is_relevant_to_me: true,
      },
    ],
    activity: [{ type: "INSTITUTION_VERIFIED", label: "Verified by ABC University", occurred_at: "2026-01-01T00:00:00Z" }],
    curation_note: "Curation note",
    eligibility_note: "Eligibility note",
    registration_note: "Registration note",
    ...overrides,
  };
}

describe("MyInstitutionView", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches the workspace once on mount", () => {
    mocks.getMyInstitutionWorkspace.mockReturnValue(new Promise(() => {}));
    render(<MyInstitutionView />);
    expect(mocks.getMyInstitutionWorkspace).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getMyInstitutionWorkspace.mockReturnValue(new Promise(() => {}));
    render(<MyInstitutionView />);
    expect(screen.getByText(/Loading your institution/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getMyInstitutionWorkspace.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<MyInstitutionView />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the connect flow (InstitutionLinkCard) when not linked", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce({
      linked: false, institution: null, profile: null,
      kpis: { placement_drives: 0, internships: 0, events: 0, active_applications: 0 },
      placement_drives: [], internships: [], events: [], activity: [],
      curation_note: "note", eligibility_note: "note", registration_note: "note",
    });
    mocks.getMyLinkRequests.mockResolvedValueOnce({ requests: [] });
    render(<MyInstitutionView />);
    expect(await screen.findByText("Institution Link")).toBeInTheDocument();
  });

  it("renders institution identity, verified badge and department/batch", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce(workspace());
    render(<MyInstitutionView />);
    expect(await screen.findByText("ABC University")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(screen.getByText("CSE")).toBeInTheDocument();
    expect(screen.getByText("Batch 2026")).toBeInTheDocument();
  });

  it("renders KPI cards", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce(workspace());
    render(<MyInstitutionView />);
    await screen.findByText("ABC University");
    expect(screen.getAllByText("Placement Drives").length).toBeGreaterThan(0);
    expect(screen.getByText("Upcoming Events")).toBeInTheDocument();
    expect(screen.getByText("Active Applications")).toBeInTheDocument();
  });

  it("renders curated internships with a link into the existing apply flow", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce(workspace());
    render(<MyInstitutionView />);
    const link = await screen.findByText("Backend Intern");
    const viewLink = link.closest("li")?.querySelector("a");
    expect(viewLink).toHaveAttribute("href", "/student/internships/internship_i1");
  });

  it("renders placement drives with eligibility and a link into the existing apply flow", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce(workspace());
    render(<MyInstitutionView />);
    const title = await screen.findByText("Campus Drive 2026");
    expect(screen.getByText("Eligible")).toBeInTheDocument();
    const viewLink = title.closest("li")?.querySelector("a");
    expect(viewLink).toHaveAttribute("href", "/student/jobs/job_j1");
  });

  it("shows ineligibility reasons instead of hiding the drive", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce(
      workspace({
        placement_drives: [
          {
            id: "pd1", title: "Campus Drive 2026", description: null, status: "OPEN",
            application_deadline: null, drive_date: null, mode: "ONSITE", venue: null,
            company_name: "Acme Corp", job_id: "j1", is_eligible: false,
            eligibility_reasons: ["CGPA below 9.5"], already_applied: false, application_status: null,
          },
        ],
      }),
    );
    render(<MyInstitutionView />);
    expect(await screen.findByText("Campus Drive 2026")).toBeInTheDocument();
    expect(screen.getByText("Not eligible")).toBeInTheDocument();
    expect(screen.getByText("CGPA below 9.5")).toBeInTheDocument();
  });

  it("shows event info without any fabricated registration/attendance data", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce(workspace());
    render(<MyInstitutionView />);
    expect(await screen.findByText("Kickoff Session")).toBeInTheDocument();
    expect(screen.getByText("Registration note")).toBeInTheDocument();
    expect(screen.queryByText(/registered/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/attendance/i)).not.toBeInTheDocument();
  });

  it("renders the activity feed", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce(workspace());
    render(<MyInstitutionView />);
    expect(await screen.findByText("Verified by ABC University")).toBeInTheDocument();
  });

  it("shows empty states when the institution has nothing yet", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce(
      workspace({
        kpis: { placement_drives: 0, internships: 0, events: 0, active_applications: 0 },
        placement_drives: [], internships: [], events: [], activity: [],
      }),
    );
    render(<MyInstitutionView />);
    expect(await screen.findByText(/has not announced any placement drives yet/i)).toBeInTheDocument();
    expect(screen.getByText("No institution-curated internships are currently available.")).toBeInTheDocument();
    expect(screen.getByText("No upcoming institution events.")).toBeInTheDocument();
  });
});
