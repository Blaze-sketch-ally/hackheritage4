import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ listMyInternshipWorkspaces: vi.fn() }));

vi.mock("@/lib/student/internship-workspace", () => ({
  listMyInternshipWorkspaces: mocks.listMyInternshipWorkspaces,
}));

import { MyInternshipsView } from "@/components/student/internship-workspace/my-internships-view";
import { WorkspaceStatusBadge } from "@/components/student/internship-workspace/workspace-status-badge";
import { ApiError } from "@/lib/api";
import {
  WORKSPACE_STATUSES,
  type InternshipWorkspaceSummary,
} from "@/types/internship-workspace";

function workspace(overrides: Partial<InternshipWorkspaceSummary> = {}): InternshipWorkspaceSummary {
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
    created_at: "2026-09-04T00:00:00Z",
    updated_at: "2026-09-04T00:00:00Z",
    internship: {
      id: "int-1",
      title: "ML Engineering Intern",
      description: null,
      work_mode: "REMOTE",
      status: "PUBLISHED",
    },
    ...overrides,
  };
}

describe("MyInternshipsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.listMyInternshipWorkspaces.mockReturnValue(new Promise(() => {}));
    render(<MyInternshipsView />);
    expect(screen.getByLabelText("Loading internships")).toBeInTheDocument();
  });

  it("shows the empty state", async () => {
    mocks.listMyInternshipWorkspaces.mockResolvedValueOnce({ workspaces: [] });
    render(<MyInternshipsView />);
    expect(await screen.findByText("No internships yet")).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.listMyInternshipWorkspaces.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<MyInternshipsView />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders each workspace with its title, work mode and status, linking to the detail page", async () => {
    mocks.listMyInternshipWorkspaces.mockResolvedValueOnce({
      workspaces: [
        workspace(),
        workspace({ id: "ws-2", work_mode: "HYBRID", workspace_status: "ACCEPTED" }),
      ],
    });
    render(<MyInternshipsView />);

    expect(await screen.findAllByText("ML Engineering Intern")).toHaveLength(2);
    expect(screen.getByText("Pending Acceptance")).toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();
    expect(screen.getByText("REMOTE")).toBeInTheDocument();
    expect(screen.getByText("HYBRID")).toBeInTheDocument();

    const links = screen.getAllByRole("button", { name: /open internship/i });
    expect(links[0]).toHaveAttribute("href", "/student/my-internships/ws-1");
    expect(links[1]).toHaveAttribute("href", "/student/my-internships/ws-2");
  });

  it("falls back to a generic title when the internship posting is no longer visible", async () => {
    mocks.listMyInternshipWorkspaces.mockResolvedValueOnce({
      workspaces: [workspace({ internship: null })],
    });
    render(<MyInternshipsView />);
    expect(await screen.findByText("Internship")).toBeInTheDocument();
  });
});

describe("WorkspaceStatusBadge", () => {
  it("renders a friendly label for every workspace status", () => {
    for (const status of WORKSPACE_STATUSES) {
      const { unmount } = render(<WorkspaceStatusBadge status={status} />);
      unmount();
    }
    render(<WorkspaceStatusBadge status="PENDING_ACCEPTANCE" />);
    expect(screen.getByText("Pending Acceptance")).toBeInTheDocument();
    render(<WorkspaceStatusBadge status="IN_PROGRESS" />);
    expect(screen.getByText("In Progress")).toBeInTheDocument();
  });
});
