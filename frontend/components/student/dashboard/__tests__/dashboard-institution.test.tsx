import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getMyInstitutionWorkspace: vi.fn(),
  getMyLinkRequests: vi.fn(),
}));

vi.mock("@/lib/student/institution", () => ({
  getMyInstitutionWorkspace: mocks.getMyInstitutionWorkspace,
}));

vi.mock("@/lib/institution-links", () => ({
  getMyLinkRequests: mocks.getMyLinkRequests,
}));

import { DashboardInstitution } from "@/components/student/dashboard/dashboard-institution";
import type { StudentInstitutionResponse } from "@/types/student-institution";

const EMPTY_WORKSPACE: StudentInstitutionResponse = {
  linked: false, institution: null, profile: null,
  kpis: { placement_drives: 0, internships: 0, events: 0, active_applications: 0 },
  placement_drives: [], internships: [], events: [], activity: [],
  curation_note: "note", eligibility_note: "note", registration_note: "note",
};

describe("DashboardInstitution", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a connect prompt when not linked and no request exists", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce(EMPTY_WORKSPACE);
    mocks.getMyLinkRequests.mockResolvedValueOnce({ requests: [] });
    render(<DashboardInstitution />);
    expect(await screen.findByText("Connect to your Institution")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /find my institution/i })).toHaveAttribute("href", "/student/institution");
  });

  it("shows a pending message when a live request exists", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce(EMPTY_WORKSPACE);
    mocks.getMyLinkRequests.mockResolvedValueOnce({
      requests: [{ id: "r1", student_id: "s1", institution_id: "inst-1", status: "PENDING", created_at: null, updated_at: null, student_name: null, student_username: null, institution_name: "ABC University" }],
    });
    render(<DashboardInstitution />);
    expect(await screen.findByText("Institution verification pending")).toBeInTheDocument();
  });

  it("shows the verified summary with counts when linked", async () => {
    mocks.getMyInstitutionWorkspace.mockResolvedValueOnce({
      ...EMPTY_WORKSPACE,
      linked: true,
      institution: { id: "inst-1", institution_name: "ABC University", institution_type: null, location: null, website_url: null },
      kpis: { placement_drives: 2, internships: 1, events: 3, active_applications: 0 },
    });
    render(<DashboardInstitution />);
    expect(await screen.findByText("ABC University")).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
    expect(mocks.getMyLinkRequests).not.toHaveBeenCalled();
    expect(screen.getByRole("button", { name: /view/i })).toHaveAttribute("href", "/student/institution");
  });

  it("shows an error state with retry on failure", async () => {
    mocks.getMyInstitutionWorkspace.mockRejectedValueOnce(new Error("network error"));
    render(<DashboardInstitution />);
    expect(await screen.findByText(/Couldn't load your institution/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
