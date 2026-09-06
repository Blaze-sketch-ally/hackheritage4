import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getJob: vi.fn(),
  updateJob: vi.fn(),
  publishJob: vi.fn(),
  closeJob: vi.fn(),
  archiveJob: vi.fn(),
  getSkillCatalog: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/jobs", () => ({
  getJob: mocks.getJob,
  updateJob: mocks.updateJob,
  publishJob: mocks.publishJob,
  closeJob: mocks.closeJob,
  archiveJob: mocks.archiveJob,
}));
vi.mock("@/lib/industry/skills", () => ({ getSkillCatalog: mocks.getSkillCatalog }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { JobDetailView } from "@/components/industry/jobs/job-detail-view";
import { ApiError } from "@/lib/api";
import type { Job } from "@/types/job";

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    industry_id: "industry-1",
    title: "Backend Engineer",
    description: "Own our API platform.",
    location: "Pune",
    work_mode: "HYBRID",
    employment_type: "FULL_TIME",
    salary_min: 1800000,
    salary_max: 2600000,
    salary_currency: "INR",
    experience_min_years: 2,
    openings: 3,
    eligibility_criteria: null,
    application_deadline: "2026-12-01",
    status: "DRAFT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    skills: [
      {
        skill_id: "s1",
        skill_name: "Python",
        category_name: "Programming",
        required_level: "Advanced",
        importance: "CORE",
      },
    ],
    ...overrides,
  };
}

describe("JobDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getJob.mockReturnValue(new Promise(() => {}));
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    render(<JobDetailView jobId="job-1" />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows a not-found message on a 404", async () => {
    mocks.getJob.mockRejectedValueOnce(new ApiError(404, "Job not found."));
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    render(<JobDetailView jobId="job-x" />);
    expect(await screen.findByText(/doesn't exist or isn't yours/i)).toBeInTheDocument();
  });

  it("renders job detail with status and skills", async () => {
    mocks.getJob.mockResolvedValueOnce(job());
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    render(<JobDetailView jobId="job-1" />);

    expect(await screen.findByRole("heading", { name: "Backend Engineer" })).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Required Skills (1)")).toBeInTheDocument();
    expect(screen.getByText("Full-time")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("switches to the edit form and saves changes", async () => {
    mocks.getJob.mockResolvedValueOnce(job());
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    mocks.updateJob.mockResolvedValueOnce(job({ title: "Staff Backend Engineer" }));

    render(<JobDetailView jobId="job-1" />);
    await screen.findByRole("heading", { name: "Backend Engineer" });

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const title = await screen.findByLabelText("Title");
    await userEvent.clear(title);
    await userEvent.type(title, "Staff Backend Engineer");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(mocks.updateJob).toHaveBeenCalledTimes(1));
    expect(mocks.updateJob.mock.calls[0][0]).toBe("job-1");
    expect(await screen.findByText("Changes saved.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Staff Backend Engineer" })).toBeInTheDocument();
  });

  it("publishes via the confirmation dialog", async () => {
    mocks.getJob.mockResolvedValueOnce(job());
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    mocks.publishJob.mockResolvedValueOnce(job({ status: "PUBLISHED" }));

    render(<JobDetailView jobId="job-1" />);
    await screen.findByRole("heading", { name: "Backend Engineer" });

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishJob).toHaveBeenCalledWith("job-1"));
    expect(await screen.findByText("Job published.")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("archives a published job via the confirmation dialog", async () => {
    mocks.getJob.mockResolvedValueOnce(job({ status: "PUBLISHED" }));
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    mocks.archiveJob.mockResolvedValueOnce(job({ status: "ARCHIVED" }));

    render(<JobDetailView jobId="job-1" />);
    await screen.findByRole("heading", { name: "Backend Engineer" });

    await userEvent.click(screen.getByRole("button", { name: "Archive" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Archive" }));

    await waitFor(() => expect(mocks.archiveJob).toHaveBeenCalledWith("job-1"));
    expect(await screen.findByText("Job archived.")).toBeInTheDocument();
  });

  it("starts in edit mode when initialEdit is set", async () => {
    mocks.getJob.mockResolvedValueOnce(job());
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    render(<JobDetailView jobId="job-1" initialEdit />);

    expect(await screen.findByRole("heading", { name: "Edit Job" })).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Backend Engineer");
  });
});
