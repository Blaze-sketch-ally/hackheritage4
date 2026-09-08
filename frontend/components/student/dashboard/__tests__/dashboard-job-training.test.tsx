import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  listMyJobTraining: vi.fn(),
}));

vi.mock("@/lib/student/job-training", () => ({
  listMyJobTraining: mocks.listMyJobTraining,
}));

import { DashboardJobTraining } from "@/components/student/dashboard/dashboard-job-training";
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
    program_title: "Onboarding",
    program_status: "PUBLISHED",
    enrollment_status: "ACTIVE",
    created_at: "2026-09-08T00:00:00Z",
    completed_at: null,
    ...overrides,
  };
}

describe("DashboardJobTraining", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders nothing while loading", () => {
    mocks.listMyJobTraining.mockReturnValue(new Promise(() => {}));
    const { container } = render(<DashboardJobTraining />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the student has no enrollments", async () => {
    mocks.listMyJobTraining.mockResolvedValueOnce({ enrollments: [] });
    const { container } = render(<DashboardJobTraining />);
    // allow the effect to resolve
    await Promise.resolve();
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when the lookup fails (no fabricated card)", async () => {
    mocks.listMyJobTraining.mockRejectedValueOnce(new ApiError(500, "down"));
    const { container } = render(<DashboardJobTraining />);
    await Promise.resolve();
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a single-program CTA straight to that program", async () => {
    mocks.listMyJobTraining.mockResolvedValueOnce({ enrollments: [enrollment()] });
    render(<DashboardJobTraining />);
    expect(await screen.findByText("Job training available")).toBeInTheDocument();
    expect(screen.getByText(/1 job training program\b/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /open training/i })).toHaveAttribute(
      "href",
      "/student/job-training/enr-1",
    );
  });

  it("shows a multi-program CTA to the list page", async () => {
    mocks.listMyJobTraining.mockResolvedValueOnce({
      enrollments: [enrollment(), enrollment({ enrollment_id: "enr-2" })],
    });
    render(<DashboardJobTraining />);
    expect(await screen.findByText(/2 job training programs/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view job training/i })).toHaveAttribute(
      "href",
      "/student/job-training",
    );
  });

  it("never fabricates progress, completion or scores", async () => {
    mocks.listMyJobTraining.mockResolvedValueOnce({ enrollments: [enrollment()] });
    render(<DashboardJobTraining />);
    await screen.findByText("Job training available");
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
    expect(screen.queryByText(/score/i)).not.toBeInTheDocument();
  });
});
