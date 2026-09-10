import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getMyJobTrainingEnrollment: vi.fn(),
}));

vi.mock("@/lib/student/job-training", () => ({
  getMyJobTrainingEnrollment: mocks.getMyJobTrainingEnrollment,
}));

import { JobTrainingDetailView } from "@/components/student/job-training/job-training-detail-view";
import { ApiError } from "@/lib/api";
import type { StudentJobTrainingDetail } from "@/types/job-training";

const EID = "enr-1";

function detail(overrides: Partial<StudentJobTrainingDetail> = {}): StudentJobTrainingDetail {
  return {
    enrollment: {
      enrollment_id: EID,
      application_id: "app-1",
      job_id: "job-1",
      job_title: "Platform Engineer",
      program_id: "prog-1",
      program_title: "Platform Onboarding",
      program_status: "PUBLISHED",
      enrollment_status: "ACTIVE",
      created_at: "2026-09-08T00:00:00Z",
      completed_at: null,
    },
    program: {
      id: "prog-1",
      job_id: "job-1",
      title: "Platform Onboarding",
      summary: "Ramp up on our platform.",
      estimated_weeks: 6,
      status: "PUBLISHED",
      published_at: "2026-09-08T00:00:00Z",
    },
    modules: [
      {
        id: "m1",
        title: "Week 1 — Fundamentals",
        description: "Start here",
        order_index: 0,
        items: [
          {
            id: "i1",
            title: "Welcome video",
            item_type: "VIDEO",
            content_url: "https://example.com/welcome",
            content_text: null,
            order_index: 0,
          },
          {
            id: "i2",
            title: "Read this",
            item_type: "TEXT",
            content_url: null,
            content_text: "Some inline reading material.",
            order_index: 1,
          },
        ],
        assignments: [
          {
            id: "as1",
            title: "Ship a small service",
            description: "Build and deploy",
            instructions: "Follow the runbook",
            assignment_type: "PROJECT",
            is_required: true,
            order_index: 0,
            due_offset_days: 14,
            submission_kind: "REPO",
            repo_required: true,
            live_url_expected: true,
            max_score: 100,
            linked_skill_id: null,
          },
        ],
      },
      {
        id: "m2",
        title: "Week 2 — Deep dive",
        description: null,
        order_index: 1,
        items: [
          {
            id: "i3",
            title: "Architecture doc",
            item_type: "PDF",
            content_url: "https://example.com/arch.pdf",
            content_text: null,
            order_index: 0,
          },
        ],
        assignments: [],
      },
    ],
    skills: [
      { skill_id: "sk-py", skill_name: "Python", requirement: "REQUIRED" },
      { skill_id: "sk-k8s", skill_name: "Kubernetes", requirement: "OPTIONAL" },
    ],
    ...overrides,
  };
}

describe("JobTrainingDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state, then the program header", async () => {
    mocks.getMyJobTrainingEnrollment.mockReturnValueOnce(new Promise(() => {}));
    const { rerender } = render(<JobTrainingDetailView enrollmentId={EID} />);
    expect(screen.getByLabelText("Loading job training program")).toBeInTheDocument();

    mocks.getMyJobTrainingEnrollment.mockResolvedValueOnce(detail());
    rerender(<JobTrainingDetailView enrollmentId={"enr-9"} />);
    expect(await screen.findByRole("heading", { name: "Platform Onboarding" })).toBeInTheDocument();
    expect(screen.getByText("Ramp up on our platform.")).toBeInTheDocument();
    expect(screen.getByText("6 weeks")).toBeInTheDocument();
    expect(mocks.getMyJobTrainingEnrollment).toHaveBeenCalledWith("enr-9");
  });

  it("renders a safe not-found state for an inaccessible enrollment (404) with no retry", async () => {
    mocks.getMyJobTrainingEnrollment.mockRejectedValueOnce(new ApiError(404, "not found"));
    render(<JobTrainingDetailView enrollmentId={EID} />);
    expect(await screen.findByText("Job training program not found.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("treats a 403 the same as not found and leaks no detail", async () => {
    mocks.getMyJobTrainingEnrollment.mockRejectedValueOnce(new ApiError(403, "forbidden"));
    render(<JobTrainingDetailView enrollmentId={EID} />);
    expect(await screen.findByText("Job training program not found.")).toBeInTheDocument();
    expect(screen.queryByText("forbidden")).not.toBeInTheDocument();
  });

  it("shows a retryable error for a 500", async () => {
    mocks.getMyJobTrainingEnrollment.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<JobTrainingDetailView enrollmentId={EID} />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders modules in order with their published items and assignments", async () => {
    mocks.getMyJobTrainingEnrollment.mockResolvedValueOnce(detail());
    render(<JobTrainingDetailView enrollmentId={EID} />);
    await screen.findByRole("heading", { name: "Platform Onboarding" });

    // module ordering: Week 1 appears in the DOM before Week 2
    const moduleTitles = screen
      .getAllByText(/Week \d/)
      .map((el) => el.textContent ?? "");
    expect(moduleTitles[0]).toContain("Week 1");
    expect(moduleTitles[1]).toContain("Week 2");

    // items
    expect(screen.getByText("Welcome video")).toBeInTheDocument();
    expect(screen.getByRole("link", { name: /watch video/i })).toHaveAttribute(
      "href",
      "https://example.com/welcome",
    );
    expect(screen.getByRole("link", { name: /open pdf/i })).toHaveAttribute(
      "href",
      "https://example.com/arch.pdf",
    );
    // TEXT item renders its content, no link
    expect(screen.getByText("Some inline reading material.")).toBeInTheDocument();
  });

  it("renders assignments read-only with no submit control", async () => {
    mocks.getMyJobTrainingEnrollment.mockResolvedValueOnce(detail());
    render(<JobTrainingDetailView enrollmentId={EID} />);
    await screen.findByRole("heading", { name: "Platform Onboarding" });

    expect(screen.getByText("Ship a small service")).toBeInTheDocument();
    expect(screen.getByText("PROJECT")).toBeInTheDocument();
    expect(screen.getByText("Required")).toBeInTheDocument();
    expect(screen.getByText(/14 days after enrollment/i)).toBeInTheDocument();
    expect(screen.getByText(/submissions aren't open yet/i)).toBeInTheDocument();

    for (const label of [/^submit/i, /upload/i, /start assignment/i]) {
      expect(screen.queryByRole("button", { name: label })).not.toBeInTheDocument();
    }
  });

  it("differentiates required and optional skills", async () => {
    mocks.getMyJobTrainingEnrollment.mockResolvedValueOnce(detail());
    render(<JobTrainingDetailView enrollmentId={EID} />);
    await screen.findByRole("heading", { name: "Platform Onboarding" });

    const requiredRow = screen.getByText("Required:").closest("div")!;
    expect(within(requiredRow).getByText("Python")).toBeInTheDocument();
    const optionalRow = screen.getByText("Optional:").closest("div")!;
    expect(within(optionalRow).getByText("Kubernetes")).toBeInTheDocument();
  });

  it("marks the experience as Job Training, not a generic 'Training'", async () => {
    mocks.getMyJobTrainingEnrollment.mockResolvedValueOnce(detail());
    render(<JobTrainingDetailView enrollmentId={EID} />);
    await screen.findByRole("heading", { name: "Platform Onboarding" });
    expect(screen.getAllByText("Job Training").length).toBeGreaterThan(0);
  });

  it("renders long assignment content without a fixed-width overflow", async () => {
    const long = "This is a very long set of assignment instructions. ".repeat(20).trim();
    mocks.getMyJobTrainingEnrollment.mockResolvedValueOnce(
      detail({
        modules: [
          {
            id: "m1",
            title: "Only module",
            description: null,
            order_index: 0,
            items: [],
            assignments: [
              {
                id: "as1",
                title: "Task",
                description: null,
                instructions: long,
                assignment_type: "ASSIGNMENT",
                is_required: false,
                order_index: 0,
                due_offset_days: null,
                submission_kind: "LINK",
                repo_required: false,
                live_url_expected: false,
                max_score: null,
                linked_skill_id: null,
              },
            ],
          },
        ],
      }),
    );
    const { container } = render(<JobTrainingDetailView enrollmentId={EID} />);
    await screen.findByText(long);
    expect(container.querySelector(".whitespace-pre-wrap")).not.toBeNull();
  });
});
