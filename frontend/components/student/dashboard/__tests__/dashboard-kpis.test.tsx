import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getSkillGap: vi.fn(),
  listMyApplications: vi.fn(),
  listMyLearningProgress: vi.fn(),
  getAttemptHistory: vi.fn(),
}));

vi.mock("@/lib/student/skill-gap", () => ({ getSkillGap: mocks.getSkillGap }));
vi.mock("@/lib/student/opportunities", () => ({ listMyApplications: mocks.listMyApplications }));
vi.mock("@/lib/student/learning", () => ({ listMyLearningProgress: mocks.listMyLearningProgress }));
vi.mock("@/lib/student/assessment", () => ({ getAttemptHistory: mocks.getAttemptHistory }));

import { DashboardKpis } from "@/components/student/dashboard/dashboard-kpis";
import { ApiError } from "@/lib/api";
import type { SkillsSummary } from "@/lib/student/dashboard";

const SKILLS: SkillsSummary = {
  total: 7,
  verified: 3,
  byLevel: { Beginner: 2, Intermediate: 2, Advanced: 2, Expert: 1 },
};

function jobRoleGap(readiness: number) {
  return {
    mode: "JOB_ROLE",
    job_role: { id: "r", name: "Backend Developer", description: null, category: null, is_active: true, created_at: "", updated_at: "" },
    readiness_percentage: readiness,
    summary: { matched: 4, needs_improvement: 1, missing: 2, unverified: 0 },
    skills: [],
    recommendations: [],
  };
}

const personalGap = {
  mode: "PERSONAL",
  counts: { total_active_skills: 7, verified_skills: 3, unverified_skills: 4, beginner_skills: 2, intermediate_skills: 2, advanced_skills: 2, expert_skills: 1 },
  progressable_skills: [],
  recommendations: [],
  prerequisite_gaps: [],
};

const OLD_MOCK_KPI_STRINGS = ["78%", "72%", "64%", "Achievements", "Badges earned"];

describe("DashboardKpis", () => {
  afterEach(() => vi.resetAllMocks());

  function arrange(opts: {
    gap?: unknown;
    apps?: unknown[];
    learning?: unknown[];
    attempts?: unknown[];
    gapError?: Error;
  }) {
    if (opts.gapError) mocks.getSkillGap.mockRejectedValue(opts.gapError);
    else mocks.getSkillGap.mockResolvedValue(opts.gap ?? personalGap);
    mocks.listMyApplications.mockResolvedValue({ applications: opts.apps ?? [] });
    mocks.listMyLearningProgress.mockResolvedValue({ progress: opts.learning ?? [] });
    mocks.getAttemptHistory.mockResolvedValue(opts.attempts ?? []);
  }

  it("renders the real skill count from props immediately (no fetch needed)", () => {
    arrange({});
    render(<DashboardKpis skills={SKILLS} />);
    expect(screen.getByText("Skills Tracked")).toBeInTheDocument();
    expect(screen.getByText("7")).toBeInTheDocument();
    expect(screen.getByText(/3 verified/)).toBeInTheDocument();
  });

  it("shows the canonical Skill Gap readiness_percentage in JOB_ROLE mode", async () => {
    arrange({
      gap: jobRoleGap(43),
      apps: [{ status: "APPLIED" }, { status: "SELECTED" }],
      learning: [{ status: "COMPLETED" }, { status: "IN_PROGRESS" }],
      attempts: [{ status: "COMPLETED", passed: true, skill_verified: true }],
    });
    render(<DashboardKpis skills={SKILLS} />);

    expect(await screen.findByText("43%")).toBeInTheDocument();
    expect(screen.getByText(/4 matched · 2 missing/)).toBeInTheDocument();
    // real learning + application + assessment numbers, all derived from the mocks
    expect(screen.getByText("Courses Completed").closest("div")?.textContent).toContain("1");
    expect(screen.getByText("Applications").closest("div")?.textContent).toContain("2");
    expect(screen.getByText("Assessments Taken").closest("div")?.textContent).toContain("1");
  });

  it("shows an honest 'Not set' for Career Readiness in PERSONAL mode (no target role)", async () => {
    arrange({ gap: personalGap });
    render(<DashboardKpis skills={SKILLS} />);
    expect(await screen.findByText("Not set")).toBeInTheDocument();
    expect(screen.getByText("Choose a target role")).toBeInTheDocument();
  });

  it("shows honest empty-state helper text when the student has no activity", async () => {
    arrange({ gap: personalGap });
    render(<DashboardKpis skills={SKILLS} />);
    expect(await screen.findByText("No applications yet")).toBeInTheDocument();
    expect(screen.getByText("None completed yet")).toBeInTheDocument();
    expect(screen.getByText("Start a course")).toBeInTheDocument();
  });

  it("degrades one failed section to 'Unavailable' without blanking the others", async () => {
    arrange({
      gapError: new ApiError(500, "boom"),
      apps: [{ status: "APPLIED" }],
    });
    render(<DashboardKpis skills={SKILLS} />);
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
    // the applications card still shows its real number
    expect(screen.getByText("Applications").closest("div")?.textContent).toContain("1");
  });

  it("a 401 (expired session) degrades to 'Unavailable' and never stays stuck on skeletons", async () => {
    arrange({
      gapError: new ApiError(401, "You must be signed in to do this."),
      apps: [{ status: "APPLIED" }, { status: "SELECTED" }],
    });
    render(<DashboardKpis skills={SKILLS} />);

    // Career Readiness resolves to the honest error state (not a fake value)
    expect(await screen.findByText("Unavailable")).toBeInTheDocument();
    // section isolation: the other cards still render their real data
    expect(screen.getByText("Applications").closest("div")?.textContent).toContain("2");
    expect(screen.getByText(/1 selected/)).toBeInTheDocument();
    // the loading skeletons are gone
    expect(document.querySelector(".animate-pulse")).toBeNull();
  });

  it("never renders any of the old hardcoded KPI values", async () => {
    arrange({ gap: jobRoleGap(50) });
    render(<DashboardKpis skills={SKILLS} />);
    await screen.findByText("50%");
    for (const s of OLD_MOCK_KPI_STRINGS) {
      expect(screen.queryByText(s)).not.toBeInTheDocument();
    }
  });
});
