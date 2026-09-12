import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getJobTrainingProgram: vi.fn(),
  createJobTrainingProgram: vi.fn(),
  updateJobTrainingProgram: vi.fn(),
  publishJobTrainingProgram: vi.fn(),
  unpublishJobTrainingProgram: vi.fn(),
  setJobTrainingProgramSkills: vi.fn(),
  createJobProgramModule: vi.fn(),
  updateJobProgramModule: vi.fn(),
  reorderJobProgramModules: vi.fn(),
  createJobProgramItem: vi.fn(),
  updateJobProgramItem: vi.fn(),
  reorderJobProgramItems: vi.fn(),
  createJobProgramAssignment: vi.fn(),
  updateJobProgramAssignment: vi.fn(),
  reorderJobProgramAssignments: vi.fn(),
}));

vi.mock("@/lib/industry/job-training", () => mocks);

import { JobTrainingProgramView } from "@/components/industry/job-training-program/job-training-program-view";
import { ApiError } from "@/lib/api";
import type { JobProgramBundle } from "@/types/job-training-program";

function bundle(overrides: Partial<JobProgramBundle> = {}): JobProgramBundle {
  return {
    job: { id: "job-1", title: "Site Reliability Engineer", status: "PUBLISHED" },
    program: {
      id: "prog-1",
      job_id: "job-1",
      title: "SRE Onboarding",
      summary: "Ramp up on reliability.",
      estimated_weeks: 8,
      status: "DRAFT",
      published_at: null,
      created_at: null,
      updated_at: null,
    },
    modules: [
      {
        id: "m1",
        title: "Foundations of Reliability",
        description: "SLIs and SLOs.",
        order_index: 0,
        is_published: true,
        items: [
          {
            id: "i1",
            module_id: "m1",
            title: "Reading: implementing SLOs",
            item_type: "LINK",
            content_url: "https://x/slo",
            content_text: null,
            order_index: 0,
            is_published: true,
          },
        ],
        assignments: [],
      },
    ],
    skills: [{ skill_id: "sk-sre", skill_name: "SRE", requirement: "REQUIRED" }],
    available_skills: [
      { skill_id: "sk-sre", skill_name: "SRE", required_level: "Advanced", importance: "CORE" },
    ],
    ...overrides,
  };
}

describe("JobTrainingProgramView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state then the program", async () => {
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle());
    render(<JobTrainingProgramView jobId="job-1" />);
    expect(screen.getByLabelText("Loading program")).toBeInTheDocument();

    expect(await screen.findByRole("heading", { name: "Job Training Program" })).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Foundations of Reliability")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /publish program/i })).toBeInTheDocument();
  });

  it("shows a 404 message for a job that isn't yours", async () => {
    mocks.getJobTrainingProgram.mockRejectedValueOnce(new ApiError(404, "nope"));
    render(<JobTrainingProgramView jobId="job-x" />);
    expect(
      await screen.findByText("This job doesn't exist or isn't yours."),
    ).toBeInTheDocument();
  });

  it("shows the no-program state and creates a program", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle({ program: null, modules: [], skills: [] }));
    mocks.createJobTrainingProgram.mockResolvedValueOnce(bundle());

    render(<JobTrainingProgramView jobId="job-1" />);
    expect(await screen.findByText("No program yet")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Program name"), "SRE Onboarding");
    await user.click(screen.getByRole("button", { name: /create program/i }));

    await waitFor(() =>
      expect(mocks.createJobTrainingProgram).toHaveBeenCalledWith("job-1", { title: "SRE Onboarding" }),
    );
    expect(await screen.findByText("Program information")).toBeInTheDocument();
  });

  it("adds a module", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle({ modules: [] }));
    mocks.createJobProgramModule.mockResolvedValueOnce(bundle());

    render(<JobTrainingProgramView jobId="job-1" />);
    await user.click(await screen.findByRole("button", { name: /add module/i }));
    await user.type(screen.getByLabelText("Module title"), "Incident Response");
    await user.click(screen.getByRole("button", { name: /^add module$/i }));

    await waitFor(() =>
      expect(mocks.createJobProgramModule).toHaveBeenCalledWith("job-1", { title: "Incident Response" }),
    );
  });

  it("adds an item to a module (URL required for a LINK)", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle());
    mocks.createJobProgramItem.mockResolvedValueOnce(bundle());

    render(<JobTrainingProgramView jobId="job-1" />);
    await user.click(await screen.findByRole("button", { name: /add item/i }));
    await user.type(screen.getByLabelText("Item title"), "On-call checklist");
    await user.type(screen.getByLabelText("URL"), "https://example.com/checklist");
    await user.click(screen.getByRole("button", { name: /^add item$/i }));

    await waitFor(() =>
      expect(mocks.createJobProgramItem).toHaveBeenCalledWith("job-1", "m1", {
        title: "On-call checklist",
        item_type: "LINK",
        content_url: "https://example.com/checklist",
        content_text: null,
      }),
    );
  });

  it("publishes the program after confirmation", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle());
    mocks.publishJobTrainingProgram.mockResolvedValueOnce(
      bundle({ program: { ...bundle().program!, status: "PUBLISHED" } }),
    );

    render(<JobTrainingProgramView jobId="job-1" />);
    await user.click(await screen.findByRole("button", { name: /publish program/i }));
    await user.click(await screen.findByRole("button", { name: /^publish$/i }));

    await waitFor(() => expect(mocks.publishJobTrainingProgram).toHaveBeenCalledWith("job-1"));
    expect(await screen.findByText(/published — you can now assign it/i)).toBeInTheDocument();
  });

  it("surfaces a publish-validation error (e.g. no published content yet)", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle());
    mocks.publishJobTrainingProgram.mockRejectedValueOnce(
      new ApiError(422, "This program isn't ready to publish. Add: at least one module."),
    );

    render(<JobTrainingProgramView jobId="job-1" />);
    await user.click(await screen.findByRole("button", { name: /publish program/i }));
    await user.click(await screen.findByRole("button", { name: /^publish$/i }));

    expect(
      await screen.findByText(/isn't ready to publish/i),
    ).toBeInTheDocument();
  });

  it("surfaces a mutation error at the top of the page", async () => {
    const user = userEvent.setup();
    mocks.getJobTrainingProgram.mockResolvedValueOnce(bundle());
    mocks.updateJobTrainingProgram.mockRejectedValueOnce(new ApiError(422, "title too long"));

    render(<JobTrainingProgramView jobId="job-1" />);
    await screen.findByText("Program information");
    await user.clear(screen.getByLabelText("Program name"));
    await user.type(screen.getByLabelText("Program name"), "Renamed");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("title too long")).toBeInTheDocument();
  });
});
