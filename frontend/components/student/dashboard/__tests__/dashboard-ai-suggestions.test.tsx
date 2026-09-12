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

import { DashboardAiSuggestions } from "@/components/student/dashboard/dashboard-ai-suggestions";
import type { CareerGuidanceResponse } from "@/types/career-guidance";

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
    learning_recommendations: [],
    youtube_videos: [],
    opportunity_recommendations: [],
    assessment_recommendations: [],
    next_actions: [
      { order: 1, type: "LEARN_SKILL", entity_type: "SKILL", entity_id: "s2", entity_name: "PostgreSQL" },
    ],
    meta: {
      provider: "groq",
      model: "test",
      ai_available: true,
      agents_used: {
        skill_gap_agent: { available: true, fallback_used: false, detail: null },
        course_agent: { available: true, fallback_used: false, detail: null },
        opportunity_agent: { available: true, fallback_used: false, detail: null },
        career_advisor: { available: true, fallback_used: false, detail: null },
      },
    },
    disclaimer: "Advisory only.",
    ...overrides,
  };
}

describe("DashboardAiSuggestions", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading skeleton, then the target role, readiness, top skill gap and next action", async () => {
    mocks.getCareerGuidance.mockResolvedValue(guidance());
    render(<DashboardAiSuggestions />);
    expect(screen.getByText("Career Readiness")).toBeInTheDocument();

    expect(await screen.findByText("Backend Developer")).toBeInTheDocument();
    expect(screen.getByText("62% ready")).toBeInTheDocument();
    expect(screen.getByText(/Top skill gap: PostgreSQL/)).toBeInTheDocument();
    expect(screen.getByText("Learn PostgreSQL")).toBeInTheDocument();
  });

  it("links its CTA to the full Career page, never a fabricated route", async () => {
    mocks.getCareerGuidance.mockResolvedValue(guidance());
    const { container } = render(<DashboardAiSuggestions />);
    await screen.findByText("Backend Developer");
    expect(container.querySelector('a[href="/student/career"]')).not.toBeNull();
  });

  it("shows an honest empty state when there is nothing to summarize yet", async () => {
    mocks.getCareerGuidance.mockResolvedValue(
      guidance({
        career_summary: { mode: "PERSONAL", target_role: null, readiness_score: null, headline: null },
        priority_skills: [],
        next_actions: [],
      }),
    );
    render(<DashboardAiSuggestions />);
    expect(await screen.findByText("Set up your career plan")).toBeInTheDocument();
    expect(screen.queryByText(/ready/)).not.toBeInTheDocument();
  });

  it("shows a retryable error state on failure, never a blank or fabricated card", async () => {
    mocks.getCareerGuidance.mockRejectedValueOnce(new Error("boom")).mockResolvedValueOnce(guidance());
    render(<DashboardAiSuggestions />);
    expect(await screen.findByText(/Couldn't load your career readiness/)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Backend Developer")).toBeInTheDocument();
  });
});
