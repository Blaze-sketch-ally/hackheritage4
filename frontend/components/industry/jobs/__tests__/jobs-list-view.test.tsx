import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getJobs: vi.fn(),
  publishJob: vi.fn(),
  closeJob: vi.fn(),
  archiveJob: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/jobs", () => ({
  getJobs: mocks.getJobs,
  publishJob: mocks.publishJob,
  closeJob: mocks.closeJob,
  archiveJob: mocks.archiveJob,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { JobsListView } from "@/components/industry/jobs/jobs-list-view";
import { ApiError } from "@/lib/api";
import type { Job } from "@/types/job";

function job(overrides: Partial<Job> = {}): Job {
  return {
    id: "job-1",
    industry_id: "industry-1",
    title: "Backend Engineer",
    description: "APIs.",
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

describe("JobsListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getJobs.mockReturnValue(new Promise(() => {}));
    render(<JobsListView />);
    expect(screen.getByText(/Loading your jobs/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getJobs.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<JobsListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no jobs", async () => {
    mocks.getJobs.mockResolvedValueOnce({ jobs: [] });
    render(<JobsListView />);
    expect(await screen.findByText("No jobs yet")).toBeInTheDocument();
  });

  it("lists jobs with title, employment type and status", async () => {
    mocks.getJobs.mockResolvedValueOnce({
      jobs: [job(), job({ id: "job-2", title: "Data Engineer", status: "PUBLISHED" })],
    });
    render(<JobsListView />);

    expect(await screen.findByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Data Engineer")).toBeInTheDocument();
    expect(screen.getAllByText("Full-time").length).toBeGreaterThan(0);
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("filters by search text", async () => {
    mocks.getJobs.mockResolvedValueOnce({
      jobs: [job(), job({ id: "job-2", title: "Data Engineer" })],
    });
    render(<JobsListView />);
    await screen.findByText("Backend Engineer");

    await userEvent.type(screen.getByLabelText("Search jobs"), "data");

    expect(screen.queryByText("Backend Engineer")).not.toBeInTheDocument();
    expect(screen.getByText("Data Engineer")).toBeInTheDocument();
  });

  it("publishes a job through the confirmation dialog", async () => {
    mocks.getJobs.mockResolvedValueOnce({ jobs: [job()] });
    mocks.publishJob.mockResolvedValueOnce(job({ status: "PUBLISHED" }));

    render(<JobsListView />);
    await screen.findByText("Backend Engineer");

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishJob).toHaveBeenCalledWith("job-1"));
    expect(await screen.findByText("Job published.")).toBeInTheDocument();
  });

  it("surfaces a publish error from the API", async () => {
    mocks.getJobs.mockResolvedValueOnce({ jobs: [job()] });
    mocks.publishJob.mockRejectedValueOnce(
      new ApiError(422, "This job isn't ready to publish. Add: employment_type."),
    );

    render(<JobsListView />);
    await screen.findByText("Backend Engineer");
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    expect(await screen.findByText(/isn't ready to publish/i)).toBeInTheDocument();
  });
});
