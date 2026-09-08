import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  listMyJobTraining: vi.fn(),
}));

vi.mock("@/lib/student/job-training", () => ({
  listMyJobTraining: mocks.listMyJobTraining,
}));

import { JobTrainingListView } from "@/components/student/job-training/job-training-list-view";
import { ApiError } from "@/lib/api";
import type { JobTrainingEnrollmentSummary } from "@/types/job-training";

function enrollment(
  overrides: Partial<JobTrainingEnrollmentSummary> = {},
): JobTrainingEnrollmentSummary {
  return {
    enrollment_id: "enr-1",
    application_id: "app-1",
    job_id: "job-1",
    job_title: "Platform Engineer",
    program_id: "prog-1",
    program_title: "Platform Onboarding",
    program_status: "PUBLISHED",
    enrollment_status: "ACTIVE",
    created_at: "2026-09-08T00:00:00Z",
    completed_at: null,
    ...overrides,
  };
}

describe("JobTrainingListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.listMyJobTraining.mockReturnValue(new Promise(() => {}));
    render(<JobTrainingListView />);
    expect(screen.getByLabelText("Loading job training")).toBeInTheDocument();
  });

  it("shows a clear empty state with a link to My Applications", async () => {
    mocks.listMyJobTraining.mockResolvedValueOnce({ enrollments: [] });
    render(<JobTrainingListView />);
    expect(await screen.findByText("No job training available")).toBeInTheDocument();
    expect(
      screen.getByText(/after you are selected for a job that has a training program/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view my applications/i })).toHaveAttribute(
      "href",
      "/student/applications",
    );
  });

  it("shows an error state with retry", async () => {
    mocks.listMyJobTraining.mockRejectedValueOnce(new ApiError(500, "server exploded"));
    render(<JobTrainingListView />);
    expect(await screen.findByText("server exploded")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders each enrollment with an Open Training CTA to its detail page", async () => {
    mocks.listMyJobTraining.mockResolvedValueOnce({
      enrollments: [
        enrollment(),
        enrollment({
          enrollment_id: "enr-2",
          job_title: "Data Engineer",
          program_title: "Data Ramp",
          enrollment_status: "COMPLETED",
          completed_at: "2026-10-01T00:00:00Z",
        }),
      ],
    });
    render(<JobTrainingListView />);

    expect(await screen.findByText("Platform Onboarding")).toBeInTheDocument();
    expect(screen.getByText("Data Ramp")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();

    const ctas = screen.getAllByRole("button", { name: /open training/i });
    expect(ctas[0]).toHaveAttribute("href", "/student/job-training/enr-1");
    expect(ctas[1]).toHaveAttribute("href", "/student/job-training/enr-2");
  });

  it("does not offer an Open Training CTA while the program is still unpublished", async () => {
    mocks.listMyJobTraining.mockResolvedValueOnce({
      enrollments: [
        enrollment({ program_id: null, program_title: null, program_status: null }),
      ],
    });
    render(<JobTrainingListView />);
    expect(await screen.findByText("Not published yet")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /open training/i })).not.toBeInTheDocument();
  });

  it("does not fabricate a company name or progress the API did not supply", async () => {
    mocks.listMyJobTraining.mockResolvedValueOnce({
      enrollments: [enrollment({ job_title: null })],
    });
    render(<JobTrainingListView />);
    await screen.findByText("Platform Onboarding");
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/complete/i)).not.toBeInTheDocument();
  });

  it("keeps a long program title from breaking the row", async () => {
    const long = "Extremely Long Job Training Program Title ".repeat(6).trim();
    mocks.listMyJobTraining.mockResolvedValueOnce({
      enrollments: [enrollment({ program_title: long })],
    });
    const { container } = render(<JobTrainingListView />);
    await screen.findByText(long);
    expect(container.querySelector(".truncate")).not.toBeNull();
  });
});
