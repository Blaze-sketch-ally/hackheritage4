import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listJobRoles, getSkillGap, setTargetJobRole, clearTargetJobRole } = vi.hoisted(() => ({
  listJobRoles: vi.fn(),
  getSkillGap: vi.fn(),
  setTargetJobRole: vi.fn(),
  clearTargetJobRole: vi.fn(),
}));

vi.mock("@/lib/student/skill-gap", () => ({ listJobRoles, getSkillGap, setTargetJobRole, clearTargetJobRole }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

// The real TargetRoleSelector renders a @base-ui/react Select, whose
// popup-open interaction is not reliably testable under jsdom in this
// project (verified separately via a live browser walkthrough). This
// stub keeps the important, testable behavior -- SkillGapView's own
// orchestration of onSelect/onClear into the right API calls and the
// right refetch -- decoupled from that third-party widget's rendering.
// TargetRoleSelector's own display logic (labels, empty state) is
// covered by its own unit test file instead.
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
      <p>{selectedJobRoleId ? `Target Role: ${jobRoles.find((r) => r.id === selectedJobRoleId)?.name}` : "No target job role selected."}</p>
      {jobRoles.length === 0 ? (
        <p>No job roles are currently available.</p>
      ) : (
        <>
          {jobRoles.map((role) => (
            <button key={role.id} onClick={() => onSelect(role.id)}>
              {role.name}
            </button>
          ))}
          {selectedJobRoleId ? <button onClick={onClear}>Clear</button> : null}
        </>
      )}
    </div>
  ),
}));

import { SkillGapView } from "@/components/student/skill-gap/skill-gap-view";
import { ApiError } from "@/lib/api";
import type {
  JobRole,
  Recommendation,
  SkillGapItem,
  SkillGapJobRoleAnalysis,
  SkillGapPersonalAnalysis,
} from "@/types/skill-gap";

function jobRole(overrides: Partial<JobRole> = {}): JobRole {
  return {
    id: "role-backend",
    name: "Backend Developer",
    description: "Builds server-side systems.",
    category: "Engineering",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function skillGapItem(overrides: Partial<SkillGapItem> = {}): SkillGapItem {
  return {
    skill_id: "skill-python",
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
    ...overrides,
  };
}

function recommendation(overrides: Partial<Recommendation> = {}): Recommendation {
  return {
    skill_id: "skill-docker",
    skill_name: "Docker",
    reason: "Docker is an important skill for Backend Developer that you haven't added yet.",
    current_level: null,
    target_level: "Beginner",
    gap: 1,
    priority: "MEDIUM",
    relationship_type: null,
    is_missing: true,
    is_verified: false,
    assessment_available: false,
    assessment_id: null,
    ...overrides,
  };
}

function jobRoleAnalysis(overrides: Partial<SkillGapJobRoleAnalysis> = {}): SkillGapJobRoleAnalysis {
  return {
    mode: "JOB_ROLE",
    job_role: jobRole(),
    readiness_percentage: 42,
    summary: { matched: 1, needs_improvement: 1, missing: 1, unverified: 1 },
    skills: [
      skillGapItem(),
      skillGapItem({
        skill_id: "skill-postgres",
        skill_name: "PostgreSQL",
        current_level: "Beginner",
        required_level: "Intermediate",
        gap: 1,
        status: "NEEDS_IMPROVEMENT",
        verification_status: "VERIFIED",
        importance: "CORE",
        priority: "MEDIUM",
      }),
      skillGapItem({
        skill_id: "skill-docker",
        skill_name: "Docker",
        current_level: null,
        required_level: "Beginner",
        gap: 1,
        status: "MISSING",
        verification_status: "UNVERIFIED",
        importance: "IMPORTANT",
        priority: "MEDIUM",
        assessment_available: true,
        assessment_id: "assessment-docker",
      }),
    ],
    recommendations: [recommendation()],
    ...overrides,
  };
}

function personalAnalysis(overrides: Partial<SkillGapPersonalAnalysis> = {}): SkillGapPersonalAnalysis {
  return {
    mode: "PERSONAL",
    counts: {
      total_active_skills: 2,
      verified_skills: 1,
      unverified_skills: 1,
      beginner_skills: 1,
      intermediate_skills: 0,
      advanced_skills: 1,
      expert_skills: 0,
    },
    progressable_skills: [],
    recommendations: [],
    prerequisite_gaps: [],
    ...overrides,
  };
}

describe("SkillGapView", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders the page header while loading", () => {
    listJobRoles.mockReturnValue(new Promise(() => {}));
    getSkillGap.mockReturnValue(new Promise(() => {}));

    render(<SkillGapView />);

    expect(screen.getByRole("heading", { name: "Skill Gap Analysis" })).toBeInTheDocument();
    expect(screen.getByText(/Loading your skill gap analysis/i)).toBeInTheDocument();
  });

  it("shows an API error state with a retry action", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));

    render(<SkillGapView />);

    expect(await screen.findByText("Backend unavailable right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows a session-expired message for a 401 with no retry button", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [] });
    getSkillGap.mockRejectedValue(new ApiError(401, "You must be signed in to do this."));

    render(<SkillGapView />);

    expect(await screen.findByText(/session has expired/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("loads job roles from the API into the target-role selector", async () => {
    listJobRoles.mockResolvedValue({
      job_roles: [jobRole(), jobRole({ id: "role-frontend", name: "Frontend Developer" })],
    });
    getSkillGap.mockResolvedValue(personalAnalysis());

    render(<SkillGapView />);

    expect(await screen.findByRole("button", { name: "Frontend Developer" })).toBeInTheDocument();
    expect(listJobRoles).toHaveBeenCalledTimes(1);
  });

  it("loads and displays the student's existing saved target role automatically", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockResolvedValue(jobRoleAnalysis());

    render(<SkillGapView />);

    expect(await screen.findByText("Target Role: Backend Developer")).toBeInTheDocument();
  });

  it("selecting a target role saves it via PUT and refreshes the analysis", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockResolvedValueOnce(personalAnalysis()).mockResolvedValueOnce(jobRoleAnalysis());
    setTargetJobRole.mockResolvedValue({ id: "target-1", job_role: jobRole() });

    render(<SkillGapView />);
    await screen.findByText("No target job role selected.");

    await userEvent.click(screen.getByRole("button", { name: "Backend Developer" }));

    await waitFor(() => expect(setTargetJobRole).toHaveBeenCalledWith("role-backend"));
    expect(await screen.findByText("Target role updated.")).toBeInTheDocument();
    expect(getSkillGap).toHaveBeenCalledTimes(2);
  });

  it("clearing the target role calls DELETE and falls back to personal analysis", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockResolvedValueOnce(jobRoleAnalysis()).mockResolvedValueOnce(personalAnalysis());
    clearTargetJobRole.mockResolvedValue(undefined);

    render(<SkillGapView />);
    await screen.findByText("Target Role: Backend Developer");

    await userEvent.click(screen.getByRole("button", { name: "Clear" }));

    await waitFor(() => expect(clearTargetJobRole).toHaveBeenCalled());
    expect(await screen.findByText("Target role cleared.")).toBeInTheDocument();
    expect(await screen.findByText("No target job role selected.")).toBeInTheDocument();
  });

  it("renders career readiness directly from the backend response", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockResolvedValue(jobRoleAnalysis({ readiness_percentage: 77 }));

    render(<SkillGapView />);

    expect(await screen.findByText("77%")).toBeInTheDocument();
  });

  it("renders matched, needs-improvement, and missing skills with their gap and verification", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockResolvedValue(jobRoleAnalysis());

    render(<SkillGapView />);
    await screen.findByText("Skill Gap");
    const table = within(screen.getByRole("table"));

    const pythonRow = table.getByText("Python").closest("tr")!;
    expect(within(pythonRow).getByText("Matched")).toBeInTheDocument();
    expect(within(pythonRow).getByText("Verified")).toBeInTheDocument();

    const postgresRow = table.getByText("PostgreSQL").closest("tr")!;
    expect(within(postgresRow).getByText("Needs Improvement")).toBeInTheDocument();
    expect(within(postgresRow).getByText("Beginner → Intermediate")).toBeInTheDocument();

    const dockerRow = table.getByText("Docker").closest("tr")!;
    expect(within(dockerRow).getByText("Missing")).toBeInTheDocument();
    expect(within(dockerRow).getByText("Not Added → Beginner")).toBeInTheDocument();
  });

  it("renders priority for each skill gap row", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockResolvedValue(jobRoleAnalysis());

    render(<SkillGapView />);
    await screen.findByText("Skill Gap");
    const dockerRow = within(screen.getByRole("table")).getByText("Docker").closest("tr")!;
    expect(within(dockerRow).getByText("MEDIUM")).toBeInTheDocument();
  });

  it("shows a Take Assessment action only when an assessment is available", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockResolvedValue(jobRoleAnalysis());

    render(<SkillGapView />);
    await screen.findByText("Skill Gap");
    const table = within(screen.getByRole("table"));

    const dockerRow = table.getByText("Docker").closest("tr")!;
    expect(within(dockerRow).getByRole("button", { name: "Take Assessment" })).toHaveAttribute(
      "href",
      "/student/assessment/assessment-docker",
    );

    const postgresRow = table.getByText("PostgreSQL").closest("tr")!;
    expect(within(postgresRow).getByText("Assessment not available yet.")).toBeInTheDocument();
  });

  it("groups and renders recommendations by priority", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockResolvedValue(
      jobRoleAnalysis({
        recommendations: [
          recommendation({ skill_id: "skill-high", skill_name: "SQL", priority: "HIGH" }),
          recommendation({ skill_id: "skill-med", skill_name: "Kubernetes", priority: "MEDIUM" }),
        ],
      }),
    );

    render(<SkillGapView />);

    expect(await screen.findByText("High Priority")).toBeInTheDocument();
    expect(screen.getByText("Medium Priority")).toBeInTheDocument();
    expect(screen.getByText("SQL")).toBeInTheDocument();
    expect(screen.getByText("Kubernetes")).toBeInTheDocument();
  });

  it("shows a personal analysis view when no target role is set", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockResolvedValue(personalAnalysis());

    render(<SkillGapView />);

    expect(await screen.findByText("Personal Skill Analysis")).toBeInTheDocument();
    expect(screen.getByText("No target job role selected.")).toBeInTheDocument();
    expect(screen.queryByText("Career Readiness")).not.toBeInTheDocument();
  });

  it("shows a no-skills empty state with an Add Skills action in personal mode", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockResolvedValue(
      personalAnalysis({ counts: { ...personalAnalysis().counts, total_active_skills: 0 } }),
    );

    render(<SkillGapView />);

    expect(await screen.findByText("You haven't added any skills yet.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Add Skills" })).toBeInTheDocument();
  });

  it("shows 'No job roles are currently available.' when the catalog is empty", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [] });
    getSkillGap.mockResolvedValue(personalAnalysis());

    render(<SkillGapView />);

    expect(await screen.findByText("No job roles are currently available.")).toBeInTheDocument();
  });

  it("shows 'No skill recommendations available yet.' when there are none", async () => {
    listJobRoles.mockResolvedValue({ job_roles: [jobRole()] });
    getSkillGap.mockResolvedValue(personalAnalysis({ recommendations: [] }));

    render(<SkillGapView />);

    expect(await screen.findByText("No skill recommendations available yet.")).toBeInTheDocument();
  });
});
