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
  });

  it("shows Not assigned + Assign Training for a published program with no prior assignment", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);

    expect(await screen.findByText("Site Reliability Engineering Onboarding")).toBeInTheDocument();
    expect(screen.getByText("Status: Not assigned")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assign Training" })).toBeInTheDocument();
  });

  it("assigns training after confirmation and flips to Training Assigned", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining.mockResolvedValueOnce({
      outcome: "CREATED",
      detail: "created",
      enrollment: { id: "enr-1" },
    });

    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);
    await user.click(await screen.findByRole("button", { name: "Assign Training" }));

    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/assigns this job's published training program/i)).toBeInTheDocument();
    await user.click(within(dialog).getByRole("button", { name: "Assign Training" }));

    expect(mocks.provisionJobTraining).toHaveBeenCalledWith("app-1");
    expect(await screen.findByText("Training Assigned")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Assign Training" })).not.toBeInTheDocument();
  });

  it("treats ALREADY_EXISTS as already assigned, not an error", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining.mockResolvedValueOnce({
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

  it("starts pre-assigned when initialProvisioning already reports a provisioned JOB_TRAINING enrollment", async () => {
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
  });

  it("shows a revoked state with no resurrection button", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(publishedProgram));
    mocks.provisionJobTraining.mockResolvedValueOnce({
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
    mocks.provisionJobTraining.mockRejectedValueOnce(new ApiError(500, "boom"));

    render(<ApplicationJobTrainingPanel applicationId="app-1" jobId="job-1" />);
    await user.click(await screen.findByRole("button", { name: "Assign Training" }));
    const dialog = await screen.findByRole("dialog");
    await user.click(within(dialog).getByRole("button", { name: "Assign Training" }));

    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Assign Training" })).toBeInTheDocument();
  });
});
