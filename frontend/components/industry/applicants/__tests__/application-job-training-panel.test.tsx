import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getJobTrainingProgram: vi.fn(),
  provisionJobTraining: vi.fn(),
}));

vi.mock("@/lib/industry/job-training", () => ({
  getJobTrainingProgram: mocks.getJobTrainingProgram,
}));
vi.mock("@/lib/industry/applications", () => ({
  provisionJobTraining: mocks.provisionJobTraining,
}));

import { ApplicationJobTrainingPanel } from "@/components/industry/applicants/application-job-training-panel";
import { ApiError } from "@/lib/api";
import type { JobProgramBundle } from "@/types/job-training-program";

function bundle(program: JobProgramBundle["program"]): JobProgramBundle {
  return {
    job: { id: "job-1", title: "Site Reliability Engineer", status: "PUBLISHED" },
    program,
    modules: [],
    skills: [],
    available_skills: [],
  };
}

const publishedProgram: JobProgramBundle["program"] = {
  id: "prog-1",
  job_id: "job-1",
  title: "Site Reliability Engineering Onboarding",
  summary: null,
  estimated_weeks: 8,
  status: "PUBLISHED",
  published_at: "2026-11-03T09:00:00Z",
  created_at: null,
  updated_at: null,
};

describe("ApplicationJobTrainingPanel", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows the no-program state with a Create Training Program link", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(null));
    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);

    expect(
      await screen.findByText("No training program published for this job yet."),
    ).toBeInTheDocument();
    const link = screen.getByRole("button", { name: "Create Training Program" });
    expect(link).toHaveAttribute("href", "/industry/jobs/job-1/training-program");
    expect(screen.queryByRole("button", { name: "Assign Training" })).not.toBeInTheDocument();
    // A missing program can never have a real enrollment -- no reason to
    // call the (write-shaped) verify endpoint at all.
    expect(mocks.provisionJobTraining).not.toHaveBeenCalled();
  });

  it("shows the draft-not-published state with an Open Training Program link", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(
      bundle({ ...publishedProgram, status: "DRAFT" }),
    );
    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);

    expect(await screen.findByText("Training program is not published yet.")).toBeInTheDocument();
    const link = screen.getByRole("button", { name: "Open Training Program" });
    expect(link).toHaveAttribute("href", "/industry/jobs/job-1/training-program");
    expect(screen.queryByRole("button", { name: "Assign Training" })).not.toBeInTheDocument();
    expect(mocks.provisionJobTraining).not.toHaveBeenCalled();
  });

  it("shows a checking state while the silent, refresh-safe verify is in flight", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining.mockReturnValue(new Promise(() => {}));
    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);

    expect(await screen.findByText(/Checking assignment status/i)).toBeInTheDocument();
    expect(screen.queryByText("Status: Not assigned")).not.toBeInTheDocument();
  });

  // --- Phase 5: the silent, on-mount verify (no initialProvisioning, no
  // click) is now what makes "Training Assigned" survive a refresh --
  // previously this exact scenario (fresh mount, no initialProvisioning)
  // defaulted straight to "Not assigned" even for a real, active
  // enrollment. ---

  it("silently confirms and shows Training Assigned on a fresh mount with no click and no initialProvisioning (refresh-safe)", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining.mockResolvedValueOnce({
      outcome: "ALREADY_EXISTS",
      detail: "An enrollment already exists.",
      enrollment: { id: "enr-1" },
    });

    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);

    expect(await screen.findByText("Training Assigned")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign Training" })).not.toBeInTheDocument();
    expect(mocks.provisionJobTraining).toHaveBeenCalledTimes(1);
    expect(mocks.provisionJobTraining).toHaveBeenCalledWith("app-1");
  });

  it("silently resolves to Not assigned when the on-mount check finds nothing eligible yet, and still offers Assign Training", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining.mockResolvedValueOnce({
      outcome: "SKIPPED_NOT_SELECTED",
      detail: "Application status is 'INTERVIEW_SCHEDULED', not 'SELECTED'.",
      enrollment: null,
    });

    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);

    expect(await screen.findByText("Status: Not assigned")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assign Training" })).toBeInTheDocument();
    expect(mocks.provisionJobTraining).toHaveBeenCalledWith("app-1");
  });

  it("silently resolves to a revoked state (no resurrection) when the on-mount check finds a revoked enrollment", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining.mockResolvedValueOnce({
      outcome: "REVOKED_BLOCKED",
      detail: "This candidate's Job Training enrollment was revoked and was not recreated.",
      enrollment: { id: "enr-1", enrollment_status: "REVOKED" },
    });

    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);

    expect(await screen.findByText(/enrollment was revoked/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign Training" })).not.toBeInTheDocument();
  });

  it("fails open to Not assigned (with the button as a safe retry) if the silent verify call itself errors", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining.mockRejectedValueOnce(new ApiError(500, "boom"));

    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);

    expect(await screen.findByText("Status: Not assigned")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assign Training" })).toBeInTheDocument();
    // The silent check's own failure is never shown as an error message --
    // only a retry via the explicit button would surface one.
    expect(screen.queryByText("boom")).not.toBeInTheDocument();
  });

  // --- Explicit "Assign Training" retry path -- still reachable whenever
  // the on-mount check itself resolved to "not assigned" (SKIPPED_* or a
  // transient failure). Each test below queues the on-mount call's own
  // result FIRST, then the explicit click's result. ---

  it("assigns training after confirmation and flips to Training Assigned", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining
      .mockResolvedValueOnce({
        outcome: "SKIPPED_NOT_SELECTED",
        detail: "not yet",
        enrollment: null,
      })
      .mockResolvedValueOnce({
        outcome: "CREATED",
        detail: "created",
        enrollment: { id: "enr-1" },
      });

    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);
    await user.click(await screen.findByRole("button", { name: "Assign Training" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/assigns this job's published training program/i)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Assign Training" }));

    expect(mocks.provisionJobTraining).toHaveBeenCalledTimes(2);
    expect(mocks.provisionJobTraining).toHaveBeenLastCalledWith("app-1");
    expect(await screen.findByText("Training Assigned")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign Training" })).not.toBeInTheDocument();
  });

  it("treats ALREADY_EXISTS (from an explicit retry) as already assigned, not an error", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining
      .mockResolvedValueOnce({ outcome: "SKIPPED_NOT_SELECTED", detail: "not yet", enrollment: null })
      .mockResolvedValueOnce({
        outcome: "ALREADY_EXISTS",
        detail: "already exists",
        enrollment: { id: "enr-1" },
      });

    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);
    await user.click(await screen.findByRole("button", { name: "Assign Training" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Assign Training" }));

    expect(await screen.findByText("Training Assigned")).toBeInTheDocument();
    expect(screen.queryByText(/error/i)).not.toBeInTheDocument();
  });

  it("starts pre-assigned when initialProvisioning already reports a provisioned JOB_TRAINING enrollment (no silent check needed)", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    render(
      <ApplicationJobTrainingPanel
        applicationId="app-1"
        jobId="job-1"
        initialProvisioning={{
          kind: "JOB_TRAINING",
          outcome: "CREATED",
          provisioned: true,
          message: "Selected — Job Training enrollment created.",
          enrollment_id: "enr-1",
        }}
      />,
    );

    expect(await screen.findByText("Training Assigned")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign Training" })).not.toBeInTheDocument();
    // Already known definitively from the live transition's own response --
    // no extra verify call.
    expect(mocks.provisionJobTraining).not.toHaveBeenCalled();
  });

  it("shows a revoked state with no resurrection button (explicit retry path)", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining
      .mockResolvedValueOnce({ outcome: "SKIPPED_NOT_SELECTED", detail: "not yet", enrollment: null })
      .mockResolvedValueOnce({
        outcome: "REVOKED_BLOCKED",
        detail: "This candidate's Job Training enrollment was revoked and was not recreated.",
        enrollment: { id: "enr-1", enrollment_status: "REVOKED" },
      });

    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);
    await user.click(await screen.findByRole("button", { name: "Assign Training" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Assign Training" }));

    expect(await screen.findByText(/enrollment was revoked/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign Training" })).not.toBeInTheDocument();
  });

  it("shows an error and lets the recruiter retry on a failed assignment", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining
      .mockResolvedValueOnce({ outcome: "SKIPPED_NOT_SELECTED", detail: "not yet", enrollment: null })
      .mockRejectedValueOnce(new ApiError(500, "boom"));

    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);
    await user.click(await screen.findByRole("button", { name: "Assign Training" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Assign Training" }));

    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assign Training" })).toBeInTheDocument();
  });
});
