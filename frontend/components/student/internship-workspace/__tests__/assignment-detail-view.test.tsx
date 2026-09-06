import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getMyWorkspaceAssignment: vi.fn(),
  submitMyWorkspaceAssignment: vi.fn(),
  listMyWorkspaceAssignments: vi.fn(),
}));

vi.mock("@/lib/student/internship-workspace", () => mocks);

import { AssignmentDetailView } from "@/components/student/internship-workspace/assignment-detail-view";
import { ApiError } from "@/lib/api";
import type {
  StudentSubmissionReview,
  WorkspaceAssignmentBase,
  WorkspaceAssignmentDetail,
  WorkspaceSubmission,
} from "@/types/internship-workspace";

function assignment(over: Partial<WorkspaceAssignmentBase> = {}): WorkspaceAssignmentBase {
  return {
    id: "a1",
    module_id: "m1",
    program_id: "prog-1",
    title: "Build a CLI tool",
    description: "Write a small command-line app.",
    instructions: "Use argparse. Ship a README.",
    assignment_type: "ASSIGNMENT",
    is_required: true,
    order_index: 0,
    due_offset_days: 7,
    submission_kind: "REPO",
    repo_required: true,
    live_url_expected: false,
    max_score: 100,
    linked_skill_id: null,
    ...over,
  };
}

function review(over: Partial<StudentSubmissionReview> = {}): StudentSubmissionReview {
  return {
    verdict: "REVISION_REQUESTED",
    feedback: "Please add authentication and update the README.",
    score: null,
    reviewed_at: "2026-09-03T00:00:00Z",
    ...over,
  };
}

function sub(
  attempt: number,
  status: string,
  reviews: StudentSubmissionReview[] = [],
): WorkspaceSubmission {
  return {
    id: `s${attempt}`,
    workspace_id: "ws-1",
    assignment_id: "a1",
    attempt_number: attempt,
    submission_status: status,
    repo_url: "https://github.com/me/old",
    live_url: null,
    attachment_url: null,
    notes: null,
    submitted_at: "2026-09-02T00:00:00Z",
    created_at: "2026-09-02T00:00:00Z",
    updated_at: "2026-09-02T00:00:00Z",
    reviews,
    latest_review: reviews[0] ?? null,
  };
}

function detail(over: Partial<WorkspaceAssignmentDetail> = {}): WorkspaceAssignmentDetail {
  return {
    assignment: assignment(),
    module: { id: "m1", title: "Fundamentals" },
    submissions: [],
    attempt_count: 0,
    can_submit: true,
    submit_blocked_reason: null,
    ...over,
  };
}

describe("AssignmentDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows the brief and a submission form when submitting is allowed", async () => {
    mocks.getMyWorkspaceAssignment.mockResolvedValueOnce(detail());
    render(<AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />);

    expect(await screen.findByRole("heading", { name: "Build a CLI tool" })).toBeInTheDocument();
    expect(screen.getByText("Use argparse. Ship a README.")).toBeInTheDocument();
    // repo_required -> repo field is labelled required, no live-url field
    expect(screen.getByLabelText(/repository url \(required\)/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/live \/ deployed url/i)).not.toBeInTheDocument();
    expect(screen.getByText("No attempts yet.")).toBeInTheDocument();
  });

  it("submits work and shows the new attempt in history (append-only)", async () => {
    const user = userEvent.setup();
    mocks.getMyWorkspaceAssignment.mockResolvedValueOnce(detail());
    mocks.submitMyWorkspaceAssignment.mockResolvedValueOnce(
      detail({
        submissions: [sub(1, "SUBMITTED")],
        attempt_count: 1,
        can_submit: false,
        submit_blocked_reason: "Your latest submission is still being reviewed.",
      }),
    );

    render(<AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />);
    await user.type(
      await screen.findByLabelText(/repository url/i),
      "https://github.com/me/cli",
    );
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    await waitFor(() =>
      expect(mocks.submitMyWorkspaceAssignment).toHaveBeenCalledWith("ws-1", "a1", {
        repo_url: "https://github.com/me/cli",
        live_url: null,
        attachment_url: null,
        notes: null,
      }),
    );
    expect(await screen.findByText("Submission received.")).toBeInTheDocument();
    expect(screen.getByText("Attempt 1")).toBeInTheDocument();
    // now blocked -- the reason replaces the form
    expect(
      screen.getByText("Your latest submission is still being reviewed."),
    ).toBeInTheDocument();
  });

  it("shows the blocked reason instead of the form when a resubmission is not allowed", async () => {
    mocks.getMyWorkspaceAssignment.mockResolvedValueOnce(
      detail({
        submissions: [sub(1, "ACCEPTED")],
        attempt_count: 1,
        can_submit: false,
        submit_blocked_reason: "This assignment has already been accepted.",
      }),
    );
    render(<AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />);

    expect(
      await screen.findByText("This assignment has already been accepted."),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^submit$/i })).not.toBeInTheDocument();
  });

  it("offers a NEW attempt (never an edit) after a revision request", async () => {
    mocks.getMyWorkspaceAssignment.mockResolvedValueOnce(
      detail({
        submissions: [sub(1, "REVISION_REQUESTED")],
        attempt_count: 1,
        can_submit: true,
      }),
    );
    render(<AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />);

    expect(await screen.findByText("Submit a new attempt")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /submit new attempt/i })).toBeInTheDocument();
  });

  it("surfaces a 409 from the backend without losing the form", async () => {
    const user = userEvent.setup();
    mocks.getMyWorkspaceAssignment.mockResolvedValueOnce(detail());
    mocks.submitMyWorkspaceAssignment.mockRejectedValueOnce(
      new ApiError(409, "your previous attempt is still under review"),
    );

    render(<AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />);
    await user.type(await screen.findByLabelText(/repository url/i), "https://x");
    await user.click(screen.getByRole("button", { name: /^submit$/i }));

    expect(
      await screen.findByText("your previous attempt is still under review"),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^submit$/i })).toBeInTheDocument();
  });

  it("404s cleanly", async () => {
    mocks.getMyWorkspaceAssignment.mockRejectedValueOnce(new ApiError(404, "nope"));
    render(<AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />);
    expect(await screen.findByText("Assignment not found.")).toBeInTheDocument();
  });

  // ---- Phase 6: the student sees the review outcome for their own attempts ----

  it("shows 'awaiting review' for a SUBMITTED attempt with no review yet", async () => {
    mocks.getMyWorkspaceAssignment.mockResolvedValueOnce(
      detail({
        submissions: [sub(1, "SUBMITTED")],
        attempt_count: 1,
        can_submit: false,
        submit_blocked_reason: "Your latest submission is still being reviewed.",
      }),
    );
    render(<AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />);
    expect(await screen.findByText(/submitted — awaiting review/i)).toBeInTheDocument();
    expect(screen.queryByText(/reviewer feedback/i)).not.toBeInTheDocument();
  });

  it("shows 'under review' while the industry is reviewing", async () => {
    mocks.getMyWorkspaceAssignment.mockResolvedValueOnce(
      detail({
        submissions: [sub(1, "UNDER_REVIEW")],
        attempt_count: 1,
        can_submit: false,
        submit_blocked_reason: "Your latest submission is still being reviewed.",
      }),
    );
    render(<AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />);
    expect(await screen.findByText(/your latest submission is under review/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^submit/i })).not.toBeInTheDocument();
  });

  it("shows the reviewer feedback and re-opens the form on REVISION_REQUESTED", async () => {
    mocks.getMyWorkspaceAssignment.mockResolvedValueOnce(
      detail({
        submissions: [sub(1, "REVISION_REQUESTED", [review()])],
        attempt_count: 1,
        can_submit: true,
      }),
    );
    render(<AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />);

    expect(await screen.findByText("Reviewer feedback")).toBeInTheDocument();
    expect(
      screen.getAllByText(/please add authentication and update the readme/i).length,
    ).toBeGreaterThan(0);
    // a NEW attempt, never an edit
    expect(screen.getByRole("button", { name: /submit new attempt/i })).toBeInTheDocument();
    // attempt 1 (with its review) stays in the history
    expect(screen.getByText("Attempt 1")).toBeInTheDocument();
  });

  it("shows an accepted state with a score and no submission form", async () => {
    mocks.getMyWorkspaceAssignment.mockResolvedValueOnce(
      detail({
        submissions: [sub(1, "ACCEPTED", [review({ verdict: "ACCEPTED", feedback: "Great job", score: 95 })])],
        attempt_count: 1,
        can_submit: false,
        submit_blocked_reason: "This assignment has already been accepted.",
      }),
    );
    render(<AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />);

    expect(await screen.findByText(/this assignment has been accepted/i)).toBeInTheDocument();
    expect(screen.getAllByText(/score: 95/i).length).toBeGreaterThan(0);
    expect(screen.queryByRole("button", { name: /submit/i })).not.toBeInTheDocument();
  });

  it("shows rejection feedback and allows a new attempt", async () => {
    mocks.getMyWorkspaceAssignment.mockResolvedValueOnce(
      detail({
        submissions: [sub(1, "REJECTED", [review({ verdict: "REJECTED", feedback: "Not close enough." })])],
        attempt_count: 1,
        can_submit: true,
      }),
    );
    render(<AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />);

    expect(await screen.findByText("Reviewer feedback")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /submit new attempt/i })).toBeInTheDocument();
  });

  it("never renders a reviewer id (the student can't see who reviewed)", async () => {
    mocks.getMyWorkspaceAssignment.mockResolvedValueOnce(
      detail({
        submissions: [sub(1, "REVISION_REQUESTED", [review()])],
        attempt_count: 1,
        can_submit: true,
      }),
    );
    const { container } = render(
      <AssignmentDetailView workspaceId="ws-1" assignmentId="a1" />,
    );
    await screen.findByText("Reviewer feedback");
    expect(container.textContent).not.toMatch(/reviewer_id|industry-\d/i);
  });
});
