import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listProgramSubmissions: vi.fn(),
  getProgramSubmission: vi.fn(),
  startProgramSubmissionReview: vi.fn(),
  reviewProgramSubmission: vi.fn(),
}));

const completionMocks = vi.hoisted(() => ({
  getWorkspaceCompletion: vi.fn(),
  verifyWorkspaceCompletion: vi.fn(),
  getWorkspaceStipend: vi.fn(),
  createWorkspaceStipend: vi.fn(),
  updateWorkspaceStipend: vi.fn(),
  approveWorkspaceStipend: vi.fn(),
  releaseWorkspaceStipend: vi.fn(),
  cancelWorkspaceStipend: vi.fn(),
}));

vi.mock("@/lib/industry/internship-program", () => mocks);
vi.mock("@/lib/industry/internship-workspaces", () => completionMocks);

import { ProgramSubmissionsView } from "@/components/industry/internship-program/program-submissions-view";
import { ApiError } from "@/lib/api";
import type {
  IndustrySubmission,
  IndustrySubmissionDetail,
  IndustrySubmissionListItem,
  SubmissionReview,
} from "@/types/internship-program";

function review(over: Partial<SubmissionReview> = {}): SubmissionReview {
  return {
    id: "rev-1",
    verdict: "REVISION_REQUESTED",
    feedback: "Add tests and a README.",
    score: null,
    reviewer_id: "industry-1",
    created_at: "2026-09-04T00:00:00Z",
    ...over,
  };
}

function item(over: Partial<IndustrySubmissionListItem> = {}): IndustrySubmissionListItem {
  return {
    id: "sub-1",
    workspace_id: "ws-1",
    assignment_id: "a1",
    attempt_number: 1,
    submission_status: "SUBMITTED",
    repo_url: "https://github.com/x/y",
    live_url: null,
    attachment_url: null,
    notes: null,
    submitted_at: "2026-09-03T00:00:00Z",
    created_at: null,
    updated_at: null,
    reviews: [],
    latest_review: null,
    student_name: "Asha Rao",
    assignment_title: "Build a CLI",
    module_title: "Fundamentals",
    attempt_count: 1,
    ...over,
  };
}

function attempt(n: number, status: string, reviews: SubmissionReview[] = []): IndustrySubmission {
  return {
    id: `sub-${n}`,
    workspace_id: "ws-1",
    assignment_id: "a1",
    attempt_number: n,
    submission_status: status,
    repo_url: "https://github.com/x/y",
    live_url: null,
    attachment_url: null,
    notes: null,
    submitted_at: "2026-09-03T00:00:00Z",
    created_at: null,
    updated_at: null,
    reviews,
    latest_review: reviews[0] ?? null,
  };
}

function detail(over: Partial<IndustrySubmissionDetail> = {}): IndustrySubmissionDetail {
  const submission = over.submission ?? attempt(1, "SUBMITTED");
  return {
    submission,
    student_name: "Asha Rao",
    assignment_title: "Build a CLI",
    module_title: "Fundamentals",
    assignment_max_score: null,
    attempts: over.attempts ?? [submission],
    ...over,
  };
}

async function openFirst(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole("button", { name: /^review$/i }));
}

describe("ProgramSubmissionsView", () => {
  afterEach(() => vi.resetAllMocks());

  // The Completion + Stipend sections fetch per-workspace on mount --
  // default them so the existing list/detail assertions are unaffected.
  beforeEach(() => {
    completionMocks.getWorkspaceCompletion.mockResolvedValue({
      workspace_id: "ws-1",
      required_count: 1,
      completed_count: 0,
      requirements_met: false,
      outstanding: [{ kind: "ASSIGNMENT", id: "a1", title: "Build a CLI" }],
      industry_verified: false,
      result: null,
      verified_at: null,
      certificate: null,
    });
    completionMocks.getWorkspaceStipend.mockResolvedValue({
      workspace_id: "ws-1",
      stipend: null,
    });
  });

  it("lists submissions with context and a Review action", async () => {
    mocks.listProgramSubmissions.mockResolvedValueOnce({
      submissions: [
        item(),
        item({ id: "sub-2", student_name: "Ben Lu", assignment_title: "Ship a service", assignment_id: "a2" }),
      ],
    });

    render(<ProgramSubmissionsView internshipId="int-1" />);

    expect(await screen.findAllByText("Build a CLI")).not.toHaveLength(0);
    expect(screen.getAllByText(/Asha Rao/).length).toBeGreaterThan(0);
    expect(screen.getAllByRole("button", { name: /^review$/i })).toHaveLength(2);
  });

  it("filters by assignment", async () => {
    const user = userEvent.setup();
    mocks.listProgramSubmissions.mockResolvedValueOnce({
      submissions: [
        item({ id: "sub-1", assignment_id: "a1", assignment_title: "Build a CLI" }),
        item({ id: "sub-2", assignment_id: "a2", assignment_title: "Ship a service" }),
      ],
    });

    render(<ProgramSubmissionsView internshipId="int-1" />);
    expect(await screen.findAllByRole("button", { name: /^review$/i })).toHaveLength(2);

    await user.selectOptions(screen.getByLabelText("Filter by assignment"), "a2");
    await waitFor(() =>
      expect(screen.getAllByRole("button", { name: /^review$/i })).toHaveLength(1),
    );
  });

  it("opens a submission and shows its full attempt history", async () => {
    const user = userEvent.setup();
    mocks.listProgramSubmissions.mockResolvedValueOnce({ submissions: [item({ attempt_count: 3 })] });
    mocks.getProgramSubmission.mockResolvedValueOnce(
      detail({
        submission: attempt(3, "SUBMITTED"),
        attempts: [attempt(3, "SUBMITTED"), attempt(2, "REVISION_REQUESTED"), attempt(1, "REJECTED")],
      }),
    );

    render(<ProgramSubmissionsView internshipId="int-1" />);
    await openFirst(user);

    await waitFor(() =>
      expect(mocks.getProgramSubmission).toHaveBeenCalledWith("int-1", "sub-1"),
    );
    expect(await screen.findByText("Attempt 3")).toBeInTheDocument();
    expect(screen.getByText("Attempt 2")).toBeInTheDocument();
    expect(screen.getByText("Attempt 1")).toBeInTheDocument();
  });

  // ---- Phase 6: review controls follow the backend state machine ----

  it("shows Start review + Accept/Request revision/Reject for a SUBMITTED attempt", async () => {
    const user = userEvent.setup();
    mocks.listProgramSubmissions.mockResolvedValueOnce({ submissions: [item()] });
    mocks.getProgramSubmission.mockResolvedValueOnce(detail({ submission: attempt(1, "SUBMITTED") }));

    render(<ProgramSubmissionsView internshipId="int-1" />);
    await openFirst(user);

    expect(await screen.findByRole("button", { name: /start review/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^accept$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /request revision/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^reject$/i })).toBeInTheDocument();
  });

  it("hides Start review once the attempt is UNDER_REVIEW", async () => {
    const user = userEvent.setup();
    mocks.listProgramSubmissions.mockResolvedValueOnce({ submissions: [item({ submission_status: "UNDER_REVIEW" })] });
    mocks.getProgramSubmission.mockResolvedValueOnce(detail({ submission: attempt(1, "UNDER_REVIEW") }));

    render(<ProgramSubmissionsView internshipId="int-1" />);
    await openFirst(user);

    expect(await screen.findByRole("button", { name: /^accept$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start review/i })).not.toBeInTheDocument();
  });

  it("shows NO review actions once a verdict has landed on the attempt", async () => {
    const user = userEvent.setup();
    mocks.listProgramSubmissions.mockResolvedValueOnce({ submissions: [item({ submission_status: "REVISION_REQUESTED" })] });
    mocks.getProgramSubmission.mockResolvedValueOnce(
      detail({ submission: attempt(1, "REVISION_REQUESTED", [review()]) }),
    );

    render(<ProgramSubmissionsView internshipId="int-1" />);
    await openFirst(user);

    expect(
      await screen.findByText(/this attempt has been reviewed/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^accept$/i })).not.toBeInTheDocument();
    // the existing review is still visible in the history
    expect(screen.getByText("Add tests and a README.")).toBeInTheDocument();
  });

  it("starts a review and refreshes to UNDER_REVIEW", async () => {
    const user = userEvent.setup();
    mocks.listProgramSubmissions
      .mockResolvedValueOnce({ submissions: [item()] })
      .mockResolvedValueOnce({ submissions: [item({ submission_status: "UNDER_REVIEW" })] });
    mocks.getProgramSubmission.mockResolvedValueOnce(detail({ submission: attempt(1, "SUBMITTED") }));
    mocks.startProgramSubmissionReview.mockResolvedValueOnce(
      detail({ submission: attempt(1, "UNDER_REVIEW") }),
    );

    render(<ProgramSubmissionsView internshipId="int-1" />);
    await openFirst(user);
    await user.click(await screen.findByRole("button", { name: /start review/i }));

    await waitFor(() =>
      expect(mocks.startProgramSubmissionReview).toHaveBeenCalledWith("int-1", "sub-1"),
    );
    expect(await screen.findByRole("button", { name: /^accept$/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /start review/i })).not.toBeInTheDocument();
  });

  it("requires feedback before a revision request can be submitted", async () => {
    const user = userEvent.setup();
    mocks.listProgramSubmissions.mockResolvedValueOnce({ submissions: [item()] });
    mocks.getProgramSubmission.mockResolvedValueOnce(detail({ submission: attempt(1, "SUBMITTED") }));

    render(<ProgramSubmissionsView internshipId="int-1" />);
    await openFirst(user);
    await user.click(await screen.findByRole("button", { name: /request revision/i }));

    const submit = screen.getByRole("button", { name: /submit request revision/i });
    expect(submit).toBeDisabled();
    await user.type(screen.getByLabelText(/feedback \(required\)/i), "Please add auth.");
    expect(submit).toBeEnabled();
  });

  it("submits a revision request with feedback and refreshes", async () => {
    const user = userEvent.setup();
    mocks.listProgramSubmissions
      .mockResolvedValueOnce({ submissions: [item()] })
      .mockResolvedValueOnce({ submissions: [item({ submission_status: "REVISION_REQUESTED" })] });
    mocks.getProgramSubmission.mockResolvedValueOnce(detail({ submission: attempt(1, "SUBMITTED") }));
    mocks.reviewProgramSubmission.mockResolvedValueOnce(
      detail({ submission: attempt(1, "REVISION_REQUESTED", [review()]) }),
    );

    render(<ProgramSubmissionsView internshipId="int-1" />);
    await openFirst(user);
    await user.click(await screen.findByRole("button", { name: /request revision/i }));
    await user.type(screen.getByLabelText(/feedback/i), "Add tests and a README.");
    await user.click(screen.getByRole("button", { name: /submit request revision/i }));

    await waitFor(() =>
      expect(mocks.reviewProgramSubmission).toHaveBeenCalledWith("int-1", "sub-1", {
        verdict: "REVISION_REQUESTED",
        feedback: "Add tests and a README.",
        score: null,
      }),
    );
    expect(await screen.findByText(/this attempt has been reviewed/i)).toBeInTheDocument();
  });

  it("offers a score field only when the assignment has a max score", async () => {
    const user = userEvent.setup();
    mocks.listProgramSubmissions.mockResolvedValueOnce({ submissions: [item()] });
    mocks.getProgramSubmission.mockResolvedValueOnce(
      detail({ submission: attempt(1, "SUBMITTED"), assignment_max_score: 100 }),
    );
    mocks.reviewProgramSubmission.mockResolvedValueOnce(detail({ submission: attempt(1, "ACCEPTED", [review({ verdict: "ACCEPTED", feedback: null, score: 88 })]) }));

    render(<ProgramSubmissionsView internshipId="int-1" />);
    await openFirst(user);
    await user.click(await screen.findByRole("button", { name: /^accept$/i }));
    await user.type(screen.getByLabelText(/score \(out of 100\)/i), "88");
    await user.click(screen.getByRole("button", { name: /submit accept/i }));

    await waitFor(() =>
      expect(mocks.reviewProgramSubmission).toHaveBeenCalledWith("int-1", "sub-1", {
        verdict: "ACCEPTED",
        feedback: null,
        score: 88,
      }),
    );
  });

  it("surfaces a 409 from the backend and keeps the controls", async () => {
    const user = userEvent.setup();
    mocks.listProgramSubmissions.mockResolvedValueOnce({ submissions: [item()] });
    mocks.getProgramSubmission.mockResolvedValueOnce(detail({ submission: attempt(1, "SUBMITTED") }));
    mocks.startProgramSubmissionReview.mockRejectedValueOnce(
      new ApiError(409, "A 'ACCEPTED' submission cannot be moved to 'UNDER_REVIEW'."),
    );

    render(<ProgramSubmissionsView internshipId="int-1" />);
    await openFirst(user);
    await user.click(await screen.findByRole("button", { name: /start review/i }));

    expect(
      await screen.findByText(/cannot be moved to 'UNDER_REVIEW'/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start review/i })).toBeInTheDocument();
  });

  it("shows an empty state", async () => {
    mocks.listProgramSubmissions.mockResolvedValueOnce({ submissions: [] });
    render(<ProgramSubmissionsView internshipId="int-1" />);
    expect(await screen.findByText("No submissions yet.")).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.listProgramSubmissions.mockRejectedValueOnce(new ApiError(500, "server sad"));
    render(<ProgramSubmissionsView internshipId="int-1" />);
    expect(await screen.findByText("server sad")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
