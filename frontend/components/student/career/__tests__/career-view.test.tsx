import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getSkillGap: vi.fn(),
  listJobRoles: vi.fn(),
  setTargetJobRole: vi.fn(),
  clearTargetJobRole: vi.fn(),
}));

vi.mock("@/lib/student/skill-gap", () => mocks);
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));
// TargetRoleSelector renders a base-ui Select whose popup isn't testable
// under jsdom in this project (see skill-gap-view.test.tsx); stub it to a
// plain <select> so the Career page's own orchestration is what's tested.
vi.mock("@/components/student/skill-gap/target-role-selector", () => ({
  TargetRoleSelector: ({
    jobRoles,
    selectedJobRoleId,
    onSelect,
    onClear,
  }: {
    jobRoles: { id: string; name: string }[];
    selectedJobRoleId: string | null;
    onSelect: (id: string) => void;
    onClear: () => void;
  }) => (
    <div>
      <p>{selectedJobRoleId ? `Target: ${jobRoles.find((r) => r.id === selectedJobRoleId)?.name}` : "No target job role selected."}</p>
      {jobRoles.map((r) => (
        <button key={r.id} onClick={() => onSelect(r.id)}>
          {r.name}
        </button>
      ))}
      {selectedJobRoleId && <button onClick={onClear}>Clear target</button>}
    </div>
  ),
}));

import { CareerView } from "@/components/student/career/career-view";
import { ApiError } from "@/lib/api";
import type { SkillGapJobRoleAnalysis, SkillGapPersonalAnalysis } from "@/types/skill-gap";

const ROLE = {
  id: "role-backend",
  name: "Backend Developer",
  description: "Builds server-side systems.",
  category: "Engineering",
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function jobRoleAnalysis(overrides: Partial<SkillGapJobRoleAnalysis> = {}): SkillGapJobRoleAnalysis {
  return {
    mode: "JOB_ROLE",
    job_role: ROLE,
    readiness_percentage: 43,
    summary: { matched: 2, needs_improvement: 1, missing: 2, unverified: 1 },
    skills: [
      {
        skill_id: "s1",
        skill_name: "Python",
        current_level: "Advanced",
        required_level: "Advanced",
        gap: 0,
        status: "MATCHED",
        verification_status: "VERIFIED",
        importance: "CORE",
        priority: "LOW",
        assessment_available: false,
        assessment_id: null,
      },
      {
        skill_id: "s2",
        skill_name: "PostgreSQL",
        current_level: "Beginner",
        required_level: "Intermediate",
        gap: 1,
        status: "NEEDS_IMPROVEMENT",
        verification_status: "UNVERIFIED",
        importance: "CORE",
        priority: "HIGH",
        assessment_available: true,
        assessment_id: "assess-pg",
      },
      {
        skill_id: "s3",
        skill_name: "Docker",
        current_level: null,
        required_level: "Beginner",
        gap: 1,
        status: "MISSING",
        verification_status: "UNVERIFIED",
        importance: "IMPORTANT",
        priority: "MEDIUM",
        assessment_available: false,
        assessment_id: null,
      },
    ],
    recommendations: [],
    ...overrides,
  };
}

const personalAnalysis: SkillGapPersonalAnalysis = {
  mode: "PERSONAL",
  counts: {
    total_active_skills: 3,
    verified_skills: 1,
    unverified_skills: 2,
    beginner_skills: 1,
    intermediate_skills: 1,
    advanced_skills: 1,
    expert_skills: 0,
  },
  progressable_skills: [],
  recommendations: [],
  prerequisite_gaps: [],
};

describe("CareerView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state, then the target role and canonical readiness", async () => {
    mocks.getSkillGap.mockResolvedValue(jobRoleAnalysis());
    mocks.listJobRoles.mockResolvedValue({ job_roles: [ROLE] });
    render(<CareerView careerGoals="Backend engineer" />);

    expect(screen.getByLabelText(/loading career workspace/i)).toBeInTheDocument();
    expect(await screen.findByText("Builds server-side systems.")).toBeInTheDocument();
    expect(screen.getByText("Builds server-side systems.")).toBeInTheDocument();
    // readiness is the engine's own number, surfaced verbatim
    expect(screen.getByText("43%")).toBeInTheDocument();
    expect(screen.getByText("Career Readiness")).toBeInTheDocument();
  });

  it("surfaces the summary counts from the canonical Skill Gap without recomputing", async () => {
    mocks.getSkillGap.mockResolvedValue(jobRoleAnalysis({ readiness_percentage: 77 }));
    mocks.listJobRoles.mockResolvedValue({ job_roles: [ROLE] });
    render(<CareerView careerGoals={null} />);
    expect(await screen.findByText("77%")).toBeInTheDocument();
    // matched / missing surfaced straight from summary
    expect(screen.getByText("Matched Skills").parentElement?.textContent).toContain("2");
    expect(screen.getByText("Missing Skills").parentElement?.textContent).toContain("2");
  });

  it("renders 'Skills to Strengthen' chips from the non-matched canonical skills only", async () => {
    mocks.getSkillGap.mockResolvedValue(jobRoleAnalysis());
    mocks.listJobRoles.mockResolvedValue({ job_roles: [ROLE] });
    render(<CareerView careerGoals={null} />);
    await screen.findByText("Builds server-side systems.");
    // the chip row (immediately after the heading) — Docker + PostgreSQL, not Python
    const heading = screen.getByText("Skills to Strengthen");
    const chipRow = heading.parentElement!.querySelector(".flex.flex-wrap.gap-2")!;
    expect(chipRow.textContent).toContain("PostgreSQL");
    expect(chipRow.textContent).toContain("Docker");
    expect(chipRow.textContent).toContain("Not added → Beginner"); // Docker
    expect(chipRow.textContent).not.toContain("Python"); // matched -> not a chip
  });

  it("shows an assessment link only for skills that actually have an assessment", async () => {
    mocks.getSkillGap.mockResolvedValue(jobRoleAnalysis());
    mocks.listJobRoles.mockResolvedValue({ job_roles: [ROLE] });
    const { container } = render(<CareerView careerGoals={null} />);
    await screen.findByText("Builds server-side systems.");
    expect(container.querySelector('a[href="/student/assessment/assess-pg"]')).not.toBeNull();
    // Docker has no assessment -> no link for it
    expect(container.querySelector('a[href="/student/assessment/null"]')).toBeNull();
  });

  it("only links to real opportunity routes (no fabricated matches)", async () => {
    mocks.getSkillGap.mockResolvedValue(jobRoleAnalysis());
    mocks.listJobRoles.mockResolvedValue({ job_roles: [ROLE] });
    const { container } = render(<CareerView careerGoals={null} />);
    await screen.findByText("Builds server-side systems.");
    expect(container.querySelector('a[href="/student/internships"]')).not.toBeNull();
    expect(container.querySelector('a[href="/student/jobs"]')).not.toBeNull();
    // no fabricated "N% match" style content
    expect(container.textContent).not.toMatch(/\d+%\s*match/i);
  });

  it("shows an honest empty state + a working selector when no target role is set", async () => {
    mocks.getSkillGap.mockResolvedValue(personalAnalysis);
    mocks.listJobRoles.mockResolvedValue({ job_roles: [ROLE] });
    mocks.setTargetJobRole.mockResolvedValue({});
    render(<CareerView careerGoals={null} />);

    expect(await screen.findByText(/No target job role selected yet/i)).toBeInTheDocument();
    // no fabricated readiness figure in personal mode
    expect(screen.queryByText("Career Readiness")).not.toBeInTheDocument();

    mocks.getSkillGap.mockResolvedValue(jobRoleAnalysis());
    await userEvent.click(screen.getByRole("button", { name: "Backend Developer" }));
    await waitFor(() => expect(mocks.setTargetJobRole).toHaveBeenCalledWith("role-backend"));
    expect(await screen.findByText("43%")).toBeInTheDocument();
  });

  it("links to the canonical Skill Gap page", async () => {
    mocks.getSkillGap.mockResolvedValue(jobRoleAnalysis());
    mocks.listJobRoles.mockResolvedValue({ job_roles: [ROLE] });
    const { container } = render(<CareerView careerGoals={null} />);
    await screen.findByText("Builds server-side systems.");
    expect(container.querySelector('a[href="/student/skill-gap"]')).not.toBeNull();
  });

  it("shows an error state with retry", async () => {
    mocks.getSkillGap.mockRejectedValueOnce(new ApiError(500, "boom")).mockResolvedValueOnce(jobRoleAnalysis());
    mocks.listJobRoles.mockResolvedValue({ job_roles: [ROLE] });
    render(<CareerView careerGoals={null} />);
    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Builds server-side systems.")).toBeInTheDocument();
  });

  it("renders the student's real career goals in the Career Direction card", async () => {
    mocks.getSkillGap.mockResolvedValue(personalAnalysis);
    mocks.listJobRoles.mockResolvedValue({ job_roles: [] });
    render(<CareerView careerGoals="Become a distributed-systems engineer" />);
    expect(await screen.findByText("Become a distributed-systems engineer")).toBeInTheDocument();
  });
});
