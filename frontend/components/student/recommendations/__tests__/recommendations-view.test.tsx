import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({ getRecommendations: vi.fn() }));

vi.mock("@/lib/student/recommendations", () => ({ getRecommendations: mocks.getRecommendations }));

import { RecommendationsView } from "@/components/student/recommendations/recommendations-view";
import { ApiError } from "@/lib/api";
import type {
  RecommendedAssessment,
  RecommendedOpportunity,
  StudentRecommendationsResponse,
} from "@/types/student-recommendation";
import type { LearningRecommendation } from "@/types/student-learning";

function assessment(overrides: Partial<RecommendedAssessment> = {}): RecommendedAssessment {
  return {
    id: "22222222-2222-2222-2222-222222222222",
    title: "Python Fundamentals",
    skill_id: "s1",
    skill_name: "Python",
    difficulty: "Beginner",
    duration_minutes: 30,
    reason_type: "NOT_ASSESSED",
    reason: "You have not demonstrated this skill yet.",
    priority: "HIGH",
    ...overrides,
  };
}

function opp(overrides: Partial<RecommendedOpportunity> = {}): RecommendedOpportunity {
  return {
    type: "INTERNSHIP",
    id: "internship_11111111-1111-1111-1111-111111111111",
    title: "Backend Intern",
    description: "Build APIs.",
    company: "Acme",
    location: "Pune",
    work_mode: "HYBRID",
    detail_path: "/student/internships/internship_11111111-1111-1111-1111-111111111111",
    match_score: 72,
    match_band: "GOOD",
    matched_skill_count: 3,
    required_skill_count: 5,
    relevant_skills: ["Python", "PostgreSQL"],
    ...overrides,
  };
}

function learning(overrides: Partial<LearningRecommendation> = {}): LearningRecommendation {
  return {
    resource: {
      id: "aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa",
      title: "Python for Everybody",
      description: "Intro.",
      url: "https://www.py4e.com/",
      provider: "py4e",
      resource_type: "COURSE",
      difficulty: "Beginner",
      estimated_minutes: 1200,
      skills: [],
      progress: null,
    },
    matched_skills: [
      { skill_id: "s1", skill_name: "Python", reason: "Core gap for your target role.", priority: "HIGH" },
    ],
    ...overrides,
  };
}

function response(overrides: Partial<StudentRecommendationsResponse> = {}): StudentRecommendationsResponse {
  return {
    mode: "AGGREGATE",
    target_role: null,
    assessments: [],
    opportunities: [],
    learning: [],
    ...overrides,
  };
}

describe("RecommendationsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getRecommendations.mockReturnValue(new Promise(() => {}));
    render(<RecommendationsView />);
    expect(screen.getByLabelText("Loading recommendations")).toBeInTheDocument();
  });

  it("renders assessment recommendations with skill, priority, and reason", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(
      response({ assessments: [assessment()] }),
    );
    render(<RecommendationsView />);

    expect(await screen.findByText("Python Fundamentals")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Not yet assessed")).toBeInTheDocument();
    expect(screen.getByText(/You have not demonstrated this skill yet\./i)).toBeInTheDocument();
  });

  it("links assessment cards to the canonical /student/assessment/[id] route", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(
      response({ assessments: [assessment()] }),
    );
    const { container } = render(<RecommendationsView />);
    await screen.findByText("Python Fundamentals");
    expect(
      container.querySelector(
        'a[href="/student/assessment/22222222-2222-2222-2222-222222222222"]',
      ),
    ).not.toBeNull();
  });

  it("shows a truthful empty state for assessments", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(response());
    render(<RecommendationsView />);
    expect(await screen.findByText("No recommended assessments yet.")).toBeInTheDocument();
  });

  it("renders opportunity recommendations with a truthful skill-count explanation", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(
      response({
        opportunities: [opp(), opp({ id: "job_2", type: "JOB", title: "Platform Engineer" })],
      }),
    );
    render(<RecommendationsView />);

    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText("Platform Engineer")).toBeInTheDocument();
    expect(screen.getAllByText(/Matches 3 of 5 skills this role needs/i).length).toBeGreaterThan(0);
  });

  it("renders learning recommendations with the canonical reason text", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(response({ learning: [learning()] }));
    render(<RecommendationsView />);
    expect(await screen.findByText("Python for Everybody")).toBeInTheDocument();
    expect(screen.getByText(/Core gap for your target role\./i)).toBeInTheDocument();
  });

  it("shows separate truthful empty states per section", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(response());
    render(<RecommendationsView />);
    expect(await screen.findByText("No recommended assessments yet.")).toBeInTheDocument();
    expect(screen.getByText("No recommended opportunities yet.")).toBeInTheDocument();
    expect(screen.getByText("No recommended learning resources yet.")).toBeInTheDocument();
  });

  it("renders no card when a section is empty", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(response({ opportunities: [opp()] }));
    const { container } = render(<RecommendationsView />);
    await screen.findByText("Backend Intern");
    // learning section empty -> no learning card link
    expect(container.querySelector('a[href^="/student/learning/"]')).toBeNull();
  });

  it("shows an error state with retry, then recovers", async () => {
    mocks.getRecommendations
      .mockRejectedValueOnce(new ApiError(500, "Server is down."))
      .mockResolvedValueOnce(response({ opportunities: [opp()] }));
    render(<RecommendationsView />);
    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
  });

  it("links opportunity cards to the canonical student opportunity route", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(response({ opportunities: [opp()] }));
    const { container } = render(<RecommendationsView />);
    await screen.findByText("Backend Intern");
    expect(
      container.querySelector(
        'a[href="/student/internships/internship_11111111-1111-1111-1111-111111111111"]',
      ),
    ).not.toBeNull();
  });

  it("links learning cards to /student/learning/[id]", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(response({ learning: [learning()] }));
    const { container } = render(<RecommendationsView />);
    await screen.findByText("Python for Everybody");
    expect(
      container.querySelector('a[href="/student/learning/aaaaaaaa-aaaa-aaaa-aaaa-aaaaaaaaaaaa"]'),
    ).not.toBeNull();
  });

  it("never renders a fabricated percentage or AI-confidence claim", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(
      response({ opportunities: [opp()], learning: [learning()] }),
    );
    const { container } = render(<RecommendationsView />);
    await screen.findByText("Backend Intern");
    expect(container.textContent).not.toMatch(/\d+%\s*match/i);
    expect(container.textContent).not.toMatch(/AI (recommended|confidence|match)/i);
    expect(container.textContent).not.toMatch(/probability|success rate|hiring chance/i);
  });
});
