import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ getJobTrainingProgram: vi.fn() }));
vi.mock("@/lib/industry/job-training", () => ({
  getJobTrainingProgram: mocks.getJobTrainingProgram,
}));

import { JobTrainingProgramLink } from "@/components/industry/job-training-program/job-training-program-link";
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

describe("JobTrainingProgramLink", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows 'Set Up Program' when no program exists", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle(null));
    render(<JobTrainingProgramLink jobId="job-1" />);
    const cta = await screen.findByRole("button", { name: "Set Up Program" });
    expect(cta).toHaveAttribute("href", "/industry/jobs/job-1/training-program");
  });

  it("shows 'Manage Program' and the status when a program exists", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(
      bundle({
        id: "p", job_id: "job-1", title: "SRE Onboarding", summary: null, estimated_weeks: null,
        status: "PUBLISHED", published_at: null, created_at: null, updated_at: null,
      }),
    );
    render(<JobTrainingProgramLink jobId="job-1" />);
    expect(await screen.findByRole("button", { name: "Manage Program" })).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("degrades to a plain link when the lookup fails", async () => {
    mocks.getJobTrainingProgram.mockRejectedValueOnce(new ApiError(500, "down"));
    render(<JobTrainingProgramLink jobId="job-1" />);
    expect(await screen.findByRole("button", { name: "Set Up Program" })).toBeInTheDocument();
  });
});
