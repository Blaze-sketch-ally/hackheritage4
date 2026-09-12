import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getCareerGuidance: vi.fn(),
}));

vi.mock("@/lib/student/career-guidance", () => ({
  getCareerGuidance: mocks.getCareerGuidance,
  describeNextAction: (action: { entity_name: string }) => `Learn ${action.entity_name}`,
}));

import { CareerGuidancePanel } from "@/components/student/career/career-guidance-panel";
import type { CareerGuidanceResponse } from "@/types/career-guidance";

const BASE_META = {
  provider: "groq" as const,
  model: "test",
  ai_available: true,
  agents_used: {
    skill_gap_agent: { available: true, fallback_used: false, detail: null },
    course_agent: { available: true, fallback_used: false, detail: null },
    opportunity_agent: { available: true, fallback_used: false, detail: null },
    career_advisor: { available: true, fallback_used: false, detail: null },
  },
};

function guidance(overrides: Partial<CareerGuidanceResponse> = {}): CareerGuidanceResponse {
  return {
    career_summary: {
      mode: "JOB_ROLE",
      target_role: "Backend Developer",
      readiness_score: 62,
      headline: "You're most of the way to Backend Developer readiness.",
    },
    priority_skills: [
      {
        skill_id: "s2",
        skill_name: "PostgreSQL",
        canonical_status: "NEEDS_IMPROVEMENT",
        canonical_priority: "HIGH",
        canonical_importance: "CORE",
        reason: "Required at Intermediate, you're at Beginner.",
        suggested_action: "Practice PostgreSQL to reach Intermediate.",
        highlighted_by_advisor: true,
      },
    ],
    learning_recommendations: [
      {
        course: {
          candidate_id: "c1",
          source_type: "INTERNAL",
          provider: "AIC Learning",
          title: "PostgreSQL Fundamentals",
          url: "https://learn.example.com/postgres",
          description: null,
          skill_ids: ["s2"],
          skill_names: ["PostgreSQL"],
          level: "BEGINNER",
          duration_text: "4 hours",
          price_text: "Free",
          rating: null,
          certificate_available: null,
          metadata_source: "internal",
          external_course_id: null,
        },
        for_skill_id: "s2",
        for_skill_name: "PostgreSQL",
        reason: "Covers exactly the gap between your current and required level.",
        highlighted_by_advisor: true,
      },
    ],
    youtube_videos: [],
    opportunity_recommendations: [
      {
        opportunity: {
          id: "internship_abc",
          source_type: "INTERNSHIP",
          title: "Backend Intern",
          description: "Work on our API.",
          location: "Remote",
          work_mode: "REMOTE",
          status: "PUBLISHED",
          industry: null,
          application_deadline: null,
          created_at: null,
          has_applied: false,
          eligibility_criteria: null,
          openings: 1,
          duration_months: 3,
          stipend_amount: null,
          stipend_currency: null,
          start_date: null,
          employment_type: null,
          salary_min: null,
          salary_max: null,
          salary_currency: null,
          experience_min_years: null,
          skills: [],
        },
        match: {
          opportunity_id: "internship_abc",
          score: 70,
          recommendation: "GOOD",
          skill_coverage: "2/3",
          required_count: 3,
          matched_count: 2,
          needs_improvement_count: 1,
          missing_count: 0,
          matched_skills: [],
          needs_improvement_skills: [],
          missing_skills: [],
        },
        reason: "Matches your strongest verified skills.",
        highlighted_by_advisor: false,
      },
    ],
    assessment_recommendations: [
      {
        skill_id: "s2",
        skill_name: "PostgreSQL",
        action: "TAKE_ASSESSMENT",
        assessment_available: true,
        note: "Verify PostgreSQL to unlock stronger matches.",
        highlighted_by_advisor: true,
      },
      {
        skill_id: "s5",
        skill_name: "Docker",
        action: "ALREADY_VERIFIED",
        assessment_available: false,
        note: "Already verified.",
        highlighted_by_advisor: false,
      },
    ],
    next_actions: [
      { order: 1, type: "LEARN_SKILL", entity_type: "SKILL", entity_id: "s2", entity_name: "PostgreSQL" },
    ],
    meta: BASE_META,
    disclaimer: "This career plan combines your canonical skill, course, and opportunity data.",
    ...overrides,
  };
}

describe("CareerGuidancePanel", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders the headline, readiness, priority skills and next actions", async () => {
    mocks.getCareerGuidance.mockResolvedValue(guidance());
    render(<CareerGuidancePanel />);
    expect(screen.getByLabelText(/loading ai career guidance/i)).toBeInTheDocument();

    expect(await screen.findByText("Backend Developer")).toBeInTheDocument();
    expect(screen.getByText("62% ready")).toBeInTheDocument();
    expect(screen.getByText(/You're most of the way/)).toBeInTheDocument();
    expect(screen.getAllByText("PostgreSQL").length).toBeGreaterThan(0);
    expect(screen.getByText("Learn PostgreSQL")).toBeInTheDocument();
  });

  it("shows the recommended course with a real, source-backed link (never a fake provider)", async () => {
    mocks.getCareerGuidance.mockResolvedValue(guidance());
    const { container } = render(<CareerGuidancePanel />);
    await screen.findByText("PostgreSQL Fundamentals");
    const link = container.querySelector('a[href="https://learn.example.com/postgres"]');
    expect(link).not.toBeNull();
  });

  it("shows the recommended opportunity's real match band and a route to its detail page", async () => {
    mocks.getCareerGuidance.mockResolvedValue(guidance());
    const { container } = render(<CareerGuidancePanel />);
    await screen.findByText("Backend Intern");
    expect(screen.getByText(/Matches 2 of 3 skills/)).toBeInTheDocument();
    expect(screen.getByText(/Good skill match/)).toBeInTheDocument();
    expect(container.querySelector('a[href="/student/internships/internship_abc"]')).not.toBeNull();
  });

  it("maps each assessment action to the server-provided CTA exactly", async () => {
    mocks.getCareerGuidance.mockResolvedValue(guidance());
    render(<CareerGuidancePanel />);
    await screen.findByText("Backend Developer");
    expect(screen.getByRole("button", { name: "Take assessment" })).toBeInTheDocument();
    expect(screen.getByText("Already verified")).toBeInTheDocument();
    // ALREADY_VERIFIED must never render as an actionable button
    expect(screen.queryByRole("button", { name: /already verified/i })).not.toBeInTheDocument();
  });

  it("surfaces a degraded-agent notice when a specialist genuinely failed", async () => {
    mocks.getCareerGuidance.mockResolvedValue(
      guidance({
        meta: {
          ...BASE_META,
          agents_used: {
            ...BASE_META.agents_used,
            course_agent: {
              available: false,
              fallback_used: true,
              detail: "Course recommendations are temporarily unavailable.",
            },
          },
        },
      }),
    );
    render(<CareerGuidancePanel />);
    expect(
      await screen.findByText("Course recommendations are temporarily unavailable."),
    ).toBeInTheDocument();
  });

  it("shows an honest empty state when there is nothing to synthesize yet", async () => {
    mocks.getCareerGuidance.mockResolvedValue(
      guidance({
        career_summary: { mode: "PERSONAL", target_role: null, readiness_score: null, headline: null },
        priority_skills: [],
        learning_recommendations: [],
        opportunity_recommendations: [],
        assessment_recommendations: [],
        next_actions: [],
      }),
    );
    render(<CareerGuidancePanel />);
    expect(
      await screen.findByText(/Add skills or pick a target role below/),
    ).toBeInTheDocument();
  });

  it("shows a retryable error state on failure", async () => {
    mocks.getCareerGuidance.mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce(guidance());
    render(<CareerGuidancePanel />);
    expect(await screen.findByText(/Couldn't load your AI career guidance/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Backend Developer")).toBeInTheDocument();
  });
});
