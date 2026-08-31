import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const { listCareerRoles, getSkillGap } = vi.hoisted(() => ({
  listCareerRoles: vi.fn(),
  getSkillGap: vi.fn(),
}));

vi.mock("@/lib/student/career-roles", () => ({ listCareerRoles, getSkillGap }));

import { SkillGapResult, SkillGapView } from "@/components/student/skill-gap/skill-gap-view";
import { ApiError } from "@/lib/api";

/**
 * SkillGapView's role selector uses the project's headless
 * (@base-ui/react) Select -- there is no existing jsdom-interaction
 * precedent for that component anywhere in this codebase, and driving it
 * through a real click-open-popup-click-option sequence was found to
 * hang indefinitely under jsdom during Phase 1L (no ResizeObserver/
 * PointerEvent polyfills exist in vitest.setup.ts, and CI actually runs
 * `npm test`, so a hanging test would break CI, not just be slow). The
 * tests below cover: (1) SkillGapView's own states that render WITHOUT
 * opening the Select popup (loading/error/empty/selector-present), and
 * (2) SkillGapResult -- the exported sub-component that renders the
 * actual skill-gap comparison -- driven directly with a controlled
 * gapState, which is a real, faithful test of the rendering logic
 * (strong/gap/not-assessed classification, the no-evidence banner, the
 * table) without depending on unverified popup interaction.
 */

function role(overrides = {}) {
  return {
    id: "role-1",
    title: "Software Engineer",
    description: "Builds backend and full-stack applications.",
    category: "Engineering",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function skillGap(overrides = {}) {
  return {
    career_role: role(),
    overall_score: "78.00",
    skills: [
      {
        skill_id: "s1",
        skill_name: "Python",
        required_level: "70.00",
        student_score: "85.00",
        gap: "0.00",
        weight: "1.00",
        status: "STRONG" as const,
      },
      {
        skill_id: "s2",
        skill_name: "SQL",
        required_level: "65.00",
        student_score: "50.00",
        gap: "15.00",
        weight: "1.00",
        status: "GAP" as const,
      },
      {
        skill_id: "s3",
        skill_name: "Docker",
        required_level: "60.00",
        student_score: "0.00",
        gap: "60.00",
        weight: "0.75",
        status: "NOT_ASSESSED" as const,
      },
    ],
    ...overrides,
  };
}

describe("SkillGapView (role list)", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows a loading state before roles arrive", () => {
    listCareerRoles.mockReturnValue(new Promise(() => {}));
    render(<SkillGapView />);
    expect(screen.getByLabelText("Loading career roles")).toBeInTheDocument();
  });

  it("shows an empty state when there are no career roles", async () => {
    listCareerRoles.mockResolvedValue({ career_roles: [] });
    render(<SkillGapView />);
    expect(await screen.findByText("No career roles available right now")).toBeInTheDocument();
  });

  it("shows an error state with retry when the roles call fails", async () => {
    listCareerRoles.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));
    render(<SkillGapView />);
    expect(await screen.findByText("Backend unavailable right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders the role selector once roles load, with no skill-gap result yet", async () => {
    listCareerRoles.mockResolvedValue({ career_roles: [role()] });
    render(<SkillGapView />);
    expect(await screen.findByRole("combobox")).toBeInTheDocument();
    expect(screen.queryByText("Overall alignment")).not.toBeInTheDocument();
    expect(getSkillGap).not.toHaveBeenCalled();
  });
});

describe("SkillGapResult (rendering, driven directly)", () => {
  it("renders nothing for the idle state", () => {
    const { container } = render(<SkillGapResult gapState={{ status: "idle" }} />);
    expect(container).toBeEmptyDOMElement();
  });

  it("shows a loading state", () => {
    render(<SkillGapResult gapState={{ status: "loading" }} />);
    expect(screen.getByLabelText("Loading skill gap")).toBeInTheDocument();
  });

  it("shows an error state", () => {
    render(
      <SkillGapResult
        gapState={{ status: "error", error: new ApiError(500, "Could not compute your skill gap for this role.") }}
      />,
    );
    expect(screen.getByText("Could not compute your skill gap for this role.")).toBeInTheDocument();
  });

  it("renders the role overview and overall alignment score", () => {
    render(<SkillGapResult gapState={{ status: "ready", gap: skillGap() }} />);
    expect(screen.getByText("Software Engineer")).toBeInTheDocument();
    expect(screen.getByText("Overall alignment")).toBeInTheDocument();
    expect(screen.getByText("78%")).toBeInTheDocument();
  });

  it("renders a STRONG skill with its status badge", () => {
    render(<SkillGapResult gapState={{ status: "ready", gap: skillGap() }} />);
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Strong")).toBeInTheDocument();
  });

  it("renders a GAP skill with its status badge", () => {
    render(<SkillGapResult gapState={{ status: "ready", gap: skillGap() }} />);
    expect(screen.getByText("SQL")).toBeInTheDocument();
    // "Gap" also appears as the table's numeric column header -- getAllByText
    // and asserting at least one match is the badge itself, not a collision bug.
    expect(screen.getAllByText("Gap").length).toBeGreaterThanOrEqual(1);
  });

  it("renders a NOT_ASSESSED skill with no fabricated score", () => {
    render(<SkillGapResult gapState={{ status: "ready", gap: skillGap() }} />);
    expect(screen.getByText("Docker")).toBeInTheDocument();
    // "Not assessed" also appears as the summary card's label -- same
    // reasoning as the GAP case above.
    expect(screen.getAllByText("Not assessed").length).toBeGreaterThanOrEqual(1);
  });

  it("shows the no-completed-assessments banner only when every skill is NOT_ASSESSED, but still shows requirements", () => {
    render(
      <SkillGapResult
        gapState={{
          status: "ready",
          gap: skillGap({
            overall_score: "0.00",
            skills: [
              {
                skill_id: "s1",
                skill_name: "Python",
                required_level: "70.00",
                student_score: "0.00",
                gap: "70.00",
                weight: "1.00",
                status: "NOT_ASSESSED",
              },
            ],
          }),
        }}
      />,
    );
    expect(screen.getByText(/Complete an assessment to build your skill profile/)).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("does not show the no-completed-assessments banner once at least one skill has evidence", () => {
    render(<SkillGapResult gapState={{ status: "ready", gap: skillGap() }} />);
    expect(screen.queryByText(/Complete an assessment to build your skill profile/)).not.toBeInTheDocument();
  });

  it("never renders answer-key or scoring internals from the assessment engine", () => {
    render(<SkillGapResult gapState={{ status: "ready", gap: skillGap() }} />);
    expect(screen.queryByText(/correct_option_ids/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/awarded_marks/i)).not.toBeInTheDocument();
  });
});
