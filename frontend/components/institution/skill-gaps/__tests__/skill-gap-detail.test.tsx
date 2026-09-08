import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getSkillGapDetail: vi.fn(),
}));

vi.mock("@/lib/institution/skill-gaps", () => ({
  getSkillGapDetail: mocks.getSkillGapDetail,
}));

import { SkillGapDetail } from "@/components/institution/skill-gaps/skill-gap-detail";
import { ApiError } from "@/lib/api";
import type { SkillGapDetail as SkillGapDetailData } from "@/types/institution-skill-gap";

function detail(overrides: Partial<SkillGapDetailData> = {}): SkillGapDetailData {
  return {
    application_id: "app-1",
    student_id: "student-1",
    full_name: "Tapan",
    username: "tapan1",
    opportunity_type: "INTERNSHIP",
    opportunity_title: "Software Engineering Intern",
    company_name: "Robotics Inc",
    status: "APPLIED",
    applied_at: "2026-01-01T00:00:00Z",
    score: 67,
    recommendation: "PARTIAL",
    skill_coverage: "2 / 3",
    matched_count: 2,
    needs_improvement_count: 0,
    missing_count: 1,
    required_count: 3,
    matched_skills: [
      {
        skill_id: "s1",
        skill_name: "Python",
        required_level: "Intermediate",
        importance: "CORE",
        candidate_has: true,
        candidate_level: "Advanced",
        candidate_verified: true,
        status: "MATCHED",
      },
      {
        skill_id: "s2",
        skill_name: "SQL",
        required_level: "Intermediate",
        importance: "IMPORTANT",
        candidate_has: true,
        candidate_level: "Intermediate",
        candidate_verified: false,
        status: "MATCHED",
      },
    ],
    needs_improvement_skills: [],
    missing_skills: [
      {
        skill_id: "s3",
        skill_name: "React",
        required_level: "Intermediate",
        importance: "IMPORTANT",
        candidate_has: false,
        candidate_level: null,
        candidate_verified: false,
        status: "MISSING",
      },
    ],
    student_skills: [
      { skill_name: "Python", proficiency_level: "Advanced", is_verified: true },
      { skill_name: "SQL", proficiency_level: "Intermediate", is_verified: false },
    ],
    ...overrides,
  };
}

describe("SkillGapDetail", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches the detail once on mount", () => {
    mocks.getSkillGapDetail.mockReturnValue(new Promise(() => {}));
    render(<SkillGapDetail applicationId="app-1" />);
    expect(mocks.getSkillGapDetail).toHaveBeenCalledWith("app-1");
  });

  it("shows a loading state", () => {
    mocks.getSkillGapDetail.mockReturnValue(new Promise(() => {}));
    render(<SkillGapDetail applicationId="app-1" />);
    expect(screen.getByText(/Loading skill gap/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getSkillGapDetail.mockRejectedValueOnce(new ApiError(404, "Application not found."));
    render(<SkillGapDetail applicationId="app-1" />);
    expect(await screen.findByText("Application not found.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("identifies both the student and the opportunity", async () => {
    mocks.getSkillGapDetail.mockResolvedValueOnce(detail());
    render(<SkillGapDetail applicationId="app-1" />);
    expect(await screen.findByText("Tapan")).toBeInTheDocument();
    expect(screen.getByText(/Robotics Inc/)).toBeInTheDocument();
    expect(screen.getByText(/Software Engineering Intern/)).toBeInTheDocument();
    expect(screen.getByText("Applied")).toBeInTheDocument();
  });

  it("shows the match percentage", async () => {
    mocks.getSkillGapDetail.mockResolvedValueOnce(detail());
    render(<SkillGapDetail applicationId="app-1" />);
    expect(await screen.findByText("67")).toBeInTheDocument();
    expect(screen.getByText("2 / 3 skills")).toBeInTheDocument();
  });

  it("shows matched and missing required skills with clear status", async () => {
    mocks.getSkillGapDetail.mockResolvedValueOnce(detail());
    render(<SkillGapDetail applicationId="app-1" />);
    expect(await screen.findByText("Matched (2)")).toBeInTheDocument();
    expect(screen.getByText("Missing (1)")).toBeInTheDocument();
    expect(screen.getByText("React")).toBeInTheDocument();
  });

  it("shows partial (needs improvement) skills when present", async () => {
    mocks.getSkillGapDetail.mockResolvedValueOnce(
      detail({
        needs_improvement_count: 1,
        needs_improvement_skills: [
          {
            skill_id: "s4",
            skill_name: "Docker",
            required_level: "Advanced",
            importance: "CORE",
            candidate_has: true,
            candidate_level: "Beginner",
            candidate_verified: true,
            status: "NEEDS_IMPROVEMENT",
          },
        ],
      }),
    );
    render(<SkillGapDetail applicationId="app-1" />);
    expect(await screen.findByText("Needs improvement (1)")).toBeInTheDocument();
    expect(screen.getByText("Docker")).toBeInTheDocument();
  });

  it("shows the student's full recorded skill list", async () => {
    mocks.getSkillGapDetail.mockResolvedValueOnce(detail());
    render(<SkillGapDetail applicationId="app-1" />);
    await screen.findByText("Tapan");
    expect(screen.getByText("Student Skills")).toBeInTheDocument();
    expect(screen.getAllByText("Python").length).toBeGreaterThan(0);
    expect(screen.getAllByText("SQL").length).toBeGreaterThan(0);
  });

  it("shows an empty state when the student has no recorded skills", async () => {
    mocks.getSkillGapDetail.mockResolvedValueOnce(detail({ student_skills: [] }));
    render(<SkillGapDetail applicationId="app-1" />);
    expect(await screen.findByText(/has not recorded any skills yet/i)).toBeInTheDocument();
  });

  it("handles an opportunity with no required skills without crashing", async () => {
    mocks.getSkillGapDetail.mockResolvedValueOnce(
      detail({
        required_count: 0,
        matched_count: 0,
        missing_count: 0,
        needs_improvement_count: 0,
        matched_skills: [],
        missing_skills: [],
      }),
    );
    render(<SkillGapDetail applicationId="app-1" />);
    expect(await screen.findByText(/no required skills on file/i)).toBeInTheDocument();
  });
});
