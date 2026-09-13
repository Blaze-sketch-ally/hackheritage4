import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getInternshipProgram: vi.fn(),
  provisionInternshipWorkspace: vi.fn(),
}));

vi.mock("@/lib/industry/internship-program", () => ({
  getInternshipProgram: mocks.getInternshipProgram,
}));
vi.mock("@/lib/industry/applications", () => ({
  provisionInternshipWorkspace: mocks.provisionInternshipWorkspace,
}));

import { ApplicationInternshipWorkspacePanel } from "@/components/industry/applicants/application-internship-workspace-panel";
import { ApiError } from "@/lib/api";
import type { InternshipProgramBundle } from "@/types/internship-program";
import type { InternshipWorkspaceSummary } from "@/types/internship-workspace";

function bundle(program: InternshipProgramBundle["program"]): InternshipProgramBundle {
  return {
    internship: { id: "int-1", title: "Backend Intern", status: "PUBLISHED" },
    program,
    modules: [],
    skills: [],
    available_skills: [],
  };
}

const publishedProgram: InternshipProgramBundle["program"] = {
  id: "prog-1",
  internship_id: "int-1",
  title: "Backend Internship Onboarding",
  summary: null,
  estimated_weeks: 8,
  status: "PUBLISHED",
  published_at: "2026-11-03T09:00:00Z",
  created_at: null,
  updated_at: null,
};

function workspace(
  overrides: Partial<InternshipWorkspaceSummary> = {},
): InternshipWorkspaceSummary {
  return {
    id: "ws-1",
    application_id: "app-1",
    internship_id: "int-1",
    student_id: "student-1",
    industry_id: "industry-1",
    work_mode: "REMOTE",
    workspace_status: "PENDING_ACCEPTANCE",
    accepted_at: null,
    started_at: null,
    completed_at: null,
    declined_at: null,
    decline_reason: null,
    rescinded_at: null,
    rescind_reason: null,
    created_at: null,
    updated_at: null,
    internship: {
      id: "int-1",
      title: "Backend Intern",
      description: null,
      work_mode: "REMOTE",
      status: "PUBLISHED",
    },
    ...overrides,
  };
}

describe("ApplicationInternshipWorkspacePanel", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows the no-program state with a Create Internship Program link", async () => {
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle(null));
    render(<ApplicationInternshipWorkspacePanel applicationId="app-1" internshipId="int-1" />);

    expect(
      await screen.findByText("No internship program created for this internship yet."),
    ).toBeInTheDocument();
    const link = screen.getByRole("button", { name: "Create Internship Program" });
    expect(link).toHaveAttribute("href", "/industry/internships/int-1/program");
    expect(mocks.provisionInternshipWorkspace).not.toHaveBeenCalled();
  });

  it("shows the draft-not-published state with an Open Internship Program link", async () => {
    mocks.getInternshipProgram.mockResolvedValueOnce(
      bundle({ ...publishedProgram, status: "DRAFT" }),
    );
    render(<ApplicationInternshipWorkspacePanel applicationId="app-1" internshipId="int-1" />);

    expect(
      await screen.findByText("Internship program is not published yet."),
    ).toBeInTheDocument();
    const link = screen.getByRole("button", { name: "Open Internship Program" });
    expect(link).toHaveAttribute("href", "/industry/internships/int-1/program");
    expect(mocks.provisionInternshipWorkspace).not.toHaveBeenCalled();
  });

  it("shows a checking state while the silent, refresh-safe verify is in flight", async () => {
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionInternshipWorkspace.mockReturnValue(new Promise(() => {}));
    render(<ApplicationInternshipWorkspacePanel applicationId="app-1" internshipId="int-1" />);

    expect(await screen.findByText(/Checking workspace status/i)).toBeInTheDocument();
  });

  it("silently confirms and shows the persisted workspace status on a fresh mount, with a working Open Workspace link (refresh-safe)", async () => {
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionInternshipWorkspace.mockResolvedValueOnce({
      outcome: "ALREADY_EXISTS",
      detail: "An internship workspace already exists for this application.",
      work_mode: "REMOTE",
      workspace: workspace({ workspace_status: "IN_PROGRESS" }),
    });

    render(<ApplicationInternshipWorkspacePanel applicationId="app-1" internshipId="int-1" />);

    expect(await screen.findByText("In Progress")).toBeInTheDocument();
    const link = screen.getByRole("button", { name: "Open Workspace" });
    expect(link).toHaveAttribute("href", "/industry/internships/int-1/submissions");
    expect(mocks.provisionInternshipWorkspace).toHaveBeenCalledTimes(1);
    expect(mocks.provisionInternshipWorkspace).toHaveBeenCalledWith("app-1");
  });

  it.each([
    ["PENDING_ACCEPTANCE", "Pending Acceptance"],
    ["ACCEPTED", "Accepted"],
    ["IN_PROGRESS", "In Progress"],
    ["COMPLETED", "Completed"],
  ] as const)("shows %s as %s with an Open Workspace link", async (status, label) => {
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionInternshipWorkspace.mockResolvedValueOnce({
      outcome: "ALREADY_EXISTS",
      detail: "exists",
      work_mode: "REMOTE",
      workspace: workspace({ workspace_status: status }),
    });

    render(<ApplicationInternshipWorkspacePanel applicationId="app-1" internshipId="int-1" />);

    expect(await screen.findByText(label)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Open Workspace" })).toBeInTheDocument();
  });

  it("shows an honest terminal note for a DECLINED workspace", async () => {
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionInternshipWorkspace.mockResolvedValueOnce({
      outcome: "ALREADY_EXISTS",
      detail: "exists",
      work_mode: "REMOTE",
      workspace: workspace({ workspace_status: "DECLINED" }),
    });

    render(<ApplicationInternshipWorkspacePanel applicationId="app-1" internshipId="int-1" />);

    expect(await screen.findByText("Declined")).toBeInTheDocument();
    expect(screen.getByText("The student declined this internship offer.")).toBeInTheDocument();
  });

  it("shows an honest terminal note for a RESCINDED workspace", async () => {
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionInternshipWorkspace.mockResolvedValueOnce({
      outcome: "ALREADY_EXISTS",
      detail: "exists",
      work_mode: "REMOTE",
      workspace: workspace({ workspace_status: "RESCINDED" }),
    });

    render(<ApplicationInternshipWorkspacePanel applicationId="app-1" internshipId="int-1" />);

    expect(await screen.findByText("Rescinded")).toBeInTheDocument();
    expect(screen.getByText("This internship offer was withdrawn.")).toBeInTheDocument();
  });

  it("shows the backend's own honest detail message (verbatim) when nothing is provisioned yet, e.g. an ONSITE internship", async () => {
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionInternshipWorkspace.mockResolvedValueOnce({
      outcome: "SKIPPED_WORK_MODE",
      detail: "Internship work_mode is 'ONSITE' -- only REMOTE or HYBRID internships get a workspace.",
      work_mode: "ONSITE",
      workspace: null,
    });

    render(<ApplicationInternshipWorkspacePanel applicationId="app-1" internshipId="int-1" />);

    expect(
      await screen.findByText(/only REMOTE or HYBRID internships get a workspace/),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open Workspace" })).not.toBeInTheDocument();
  });

  it("shows an honest error message if the silent verify call itself fails", async () => {
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionInternshipWorkspace.mockRejectedValueOnce(new ApiError(500, "boom"));

    render(<ApplicationInternshipWorkspacePanel applicationId="app-1" internshipId="int-1" />);

    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Open Workspace" })).not.toBeInTheDocument();
  });
});
