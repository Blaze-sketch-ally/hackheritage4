import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  listMyWorkspaceAssignments: vi.fn(),
  getMyWorkspaceAssignment: vi.fn(),
  submitMyWorkspaceAssignment: vi.fn(),
}));

vi.mock("@/lib/student/internship-workspace", () => mocks);

import { WorkspaceAssignments } from "@/components/student/internship-workspace/workspace-assignments";
import { ApiError } from "@/lib/api";
import type { WorkspaceAssignmentSummary } from "@/types/internship-workspace";

function a(over: Partial<WorkspaceAssignmentSummary> = {}): WorkspaceAssignmentSummary {
  return {
    id: "a1",
    module_id: "m1",
    program_id: "prog-1",
    title: "Build a CLI",
    description: null,
    instructions: null,
    assignment_type: "ASSIGNMENT",
    is_required: true,
    order_index: 0,
    due_offset_days: null,
    submission_kind: "REPO",
    repo_required: true,
    live_url_expected: false,
    max_score: null,
    linked_skill_id: null,
    module_title: "Fundamentals",
    module_order_index: 0,
    attempt_count: 0,
    latest_submission: null,
    can_submit: true,
    submit_blocked_reason: null,
    ...over,
  };
}

describe("WorkspaceAssignments", () => {
  afterEach(() => vi.resetAllMocks());

  it("lists published assignments grouped by module, with links and status", async () => {
    mocks.listMyWorkspaceAssignments.mockResolvedValueOnce({
      assignments: [
        a({ id: "a1", title: "Build a CLI", module_title: "Fundamentals" }),
        a({
          id: "a2",
          title: "Ship a service",
          module_title: "Projects",
          attempt_count: 2,
          latest_submission: {
            id: "s2",
            workspace_id: "ws-1",
            assignment_id: "a2",
            attempt_number: 2,
            submission_status: "SUBMITTED",
            repo_url: null,
            live_url: null,
            attachment_url: null,
            notes: null,
            submitted_at: null,
            created_at: null,
            updated_at: null,
            reviews: [],
            latest_review: null,
          },
          can_submit: false,
          submit_blocked_reason: "Your latest submission is still being reviewed.",
        }),
      ],
    });

    render(<WorkspaceAssignments workspaceId="ws-1" />);

    const cli = await screen.findByRole("link", { name: /build a cli/i });
    expect(cli).toHaveAttribute(
      "href",
      "/student/my-internships/ws-1/assignments/a1",
    );
    expect(screen.getByText("Fundamentals")).toBeInTheDocument();
    expect(screen.getByText("Projects")).toBeInTheDocument();
    expect(screen.getByText("Submitted")).toBeInTheDocument();
    expect(screen.getByText(/2 attempts/i)).toBeInTheDocument();
  });

  it("shows an empty state when nothing is published", async () => {
    mocks.listMyWorkspaceAssignments.mockResolvedValueOnce({ assignments: [] });
    render(<WorkspaceAssignments workspaceId="ws-1" />);
    expect(
      await screen.findByText(/no assignments have been published/i),
    ).toBeInTheDocument();
  });

  it("shows an error message on failure", async () => {
    mocks.listMyWorkspaceAssignments.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<WorkspaceAssignments workspaceId="ws-1" />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
  });
});
