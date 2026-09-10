import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({ getApplicationMatch: vi.fn() }));

vi.mock("@/lib/industry/applications", () => ({
  getApplicationMatch: mocks.getApplicationMatch,
}));

import { MatchScore } from "@/components/industry/match-score";
import { ApiError } from "@/lib/api";
import type { ApplicationMatch, MatchSkill } from "@/types/application";

function skill(overrides: Partial<MatchSkill> = {}): MatchSkill {
  return {
    skill_id: "s1",
    skill_name: "Python",
    required_level: "Advanced",
    importance: "CORE",
    candidate_has: true,
    candidate_level: "Advanced",
    candidate_verified: true,
    status: "MATCHED",
    ...overrides,
  };
}

function match(overrides: Partial<ApplicationMatch> = {}): ApplicationMatch {
  return {
    application_id: "app-1",
    score: 72,
    recommendation: "GOOD",
    skill_coverage: "3 / 4",
    required_count: 4,
    matched_count: 2,
    needs_improvement_count: 1,
    missing_count: 1,
    matched_skills: [
      skill(),
      skill({ skill_id: "s2", skill_name: "SQL", importance: "IMPORTANT" }),
    ],
    needs_improvement_skills: [
      skill({
        skill_id: "s3",
        skill_name: "Docker",
        required_level: "Advanced",
        candidate_level: "Beginner",
        candidate_verified: false,
        status: "NEEDS_IMPROVEMENT",
      }),
    ],
    missing_skills: [
      skill({
        skill_id: "s4",
        skill_name: "Kubernetes",
        candidate_has: false,
        candidate_level: null,
        candidate_verified: false,
        status: "MISSING",
      }),
    ],
    ...overrides,
  };
}

describe("MatchScore", () => {
  afterEach(() => vi.resetAllMocks());

  it("starts idle with a Calculate action and does not call the API", () => {
    render(<MatchScore applicationId="app-1" />);
    expect(screen.getByRole("button", { name: /calculate skill match/i })).toBeInTheDocument();
    expect(mocks.getApplicationMatch).not.toHaveBeenCalled();
  });

  it("shows a loading state while calculating", async () => {
    mocks.getApplicationMatch.mockReturnValue(new Promise(() => {}));
    render(<MatchScore applicationId="app-1" />);
    await userEvent.click(screen.getByRole("button", { name: /calculate skill match/i }));
    expect(screen.getByText(/Calculating/i)).toBeInTheDocument();
    expect(mocks.getApplicationMatch).toHaveBeenCalledWith("app-1");
  });

  it("renders the score, recommendation and skill coverage on success", async () => {
    mocks.getApplicationMatch.mockResolvedValueOnce(match());
    render(<MatchScore applicationId="app-1" />);
    await userEvent.click(screen.getByRole("button", { name: /calculate skill match/i }));

    expect(await screen.findByText("72")).toBeInTheDocument();
    expect(screen.getByText("Good match")).toBeInTheDocument();
    expect(screen.getByText("3 / 4 skills")).toBeInTheDocument();
    const bar = screen.getByRole("progressbar", { name: /skill match score 72 out of 100/i });
    expect(bar).toHaveAttribute("aria-valuenow", "72");
  });

  it("renders matched, needs-improvement and missing skill groups", async () => {
    mocks.getApplicationMatch.mockResolvedValueOnce(match());
    render(<MatchScore applicationId="app-1" />);
    await userEvent.click(screen.getByRole("button", { name: /calculate skill match/i }));
    await screen.findByText("72");

    expect(screen.getByText("Matched (2)")).toBeInTheDocument();
    expect(screen.getByText("Needs improvement (1)")).toBeInTheDocument();
    expect(screen.getByText("Missing (1)")).toBeInTheDocument();

    expect(screen.getByText("Python")).toBeInTheDocument();
    const docker = screen.getByText("Docker").closest("li")!;
    expect(within(docker).getByText(/candidate declares Beginner/i)).toBeInTheDocument();
    expect(within(docker).getByText("Self-reported")).toBeInTheDocument();
    const k8s = screen.getByText("Kubernetes").closest("li")!;
    expect(within(k8s).getByText(/has not declared this skill/i)).toBeInTheDocument();
  });

  it("shows an advisory disclaimer, not a hiring-decision framing", async () => {
    mocks.getApplicationMatch.mockResolvedValueOnce(match());
    render(<MatchScore applicationId="app-1" />);
    await userEvent.click(screen.getByRole("button", { name: /calculate skill match/i }));
    expect(await screen.findByText(/not a hiring decision/i)).toBeInTheDocument();
  });

  it("shows a friendly error and retries", async () => {
    mocks.getApplicationMatch
      .mockRejectedValueOnce(new ApiError(500, "Could not calculate the match. Please try again."))
      .mockResolvedValueOnce(match({ score: 88, recommendation: "STRONG" }));
    render(<MatchScore applicationId="app-1" />);

    await userEvent.click(screen.getByRole("button", { name: /calculate skill match/i }));
    expect(await screen.findByText(/Could not calculate the match/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("88")).toBeInTheDocument();
    expect(screen.getByText("Strong match")).toBeInTheDocument();
  });

  it("handles the zero-required-skills case without a misleading 0% or recommendation", async () => {
    mocks.getApplicationMatch.mockResolvedValueOnce(
      match({
        score: 0,
        recommendation: "LOW",
        required_count: 0,
        skill_coverage: "0 / 0",
        matched_skills: [],
        needs_improvement_skills: [],
        missing_skills: [],
      }),
    );
    render(<MatchScore applicationId="app-1" />);
    await userEvent.click(screen.getByRole("button", { name: /calculate skill match/i }));

    expect(await screen.findByText("Match unavailable")).toBeInTheDocument();
    expect(screen.getByText(/Add required skills to it/i)).toBeInTheDocument();
    expect(screen.queryByText("Low match")).not.toBeInTheDocument();
    expect(screen.queryByRole("progressbar")).not.toBeInTheDocument();
  });

  it("recalculation replaces the previous result", async () => {
    mocks.getApplicationMatch
      .mockResolvedValueOnce(match({ score: 40, recommendation: "PARTIAL" }))
      .mockResolvedValueOnce(match({ score: 91, recommendation: "STRONG" }));
    render(<MatchScore applicationId="app-1" />);

    await userEvent.click(screen.getByRole("button", { name: /calculate skill match/i }));
    expect(await screen.findByText("40")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /recalculate/i }));
    expect(await screen.findByText("91")).toBeInTheDocument();
    expect(screen.queryByText("40")).not.toBeInTheDocument();
    expect(mocks.getApplicationMatch).toHaveBeenCalledTimes(2);
  });
});
