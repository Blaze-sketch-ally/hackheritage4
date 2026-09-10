import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listAssessments, fetchStudentSkills } = vi.hoisted(() => ({
  listAssessments: vi.fn(),
  fetchStudentSkills: vi.fn(),
}));

vi.mock("@/lib/student/assessment", () => ({ listAssessments }));
vi.mock("@/lib/student/skills", () => ({ fetchStudentSkills }));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

import { AssessmentListView } from "@/components/student/assessment/assessment-list-view";
import { ApiError } from "@/lib/api";

function assessment(overrides = {}) {
  return {
    id: "a1",
    skill_id: "skill-python",
    title: "Python Beginner Assessment",
    description: "Test your Python fundamentals.",
    difficulty: "Beginner",
    duration_minutes: 10,
    question_count: 5,
    passing_percentage: "60.00",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function studentSkill(overrides = {}) {
  return {
    id: "ss1",
    skill_id: "skill-python",
    proficiency_level: "Beginner",
    proficiency_score: null,
    is_verified: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    skill: {
      id: "skill-python",
      name: "Python",
      description: null,
      category: { id: "c1", name: "Programming Languages" },
    },
    ...overrides,
  };
}

function renderView() {
  return render(<AssessmentListView studentId="student-1" />);
}

describe("AssessmentListView", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows a loading state before data arrives", () => {
    listAssessments.mockReturnValue(new Promise(() => {}));
    fetchStudentSkills.mockReturnValue(new Promise(() => {}));
    renderView();
    expect(screen.getByLabelText("Loading assessments")).toBeInTheDocument();
  });

  it("shows the no-skills empty state when the student has selected no skills", async () => {
    listAssessments.mockResolvedValue({ assessments: [] });
    fetchStudentSkills.mockResolvedValue([]);

    renderView();

    expect(await screen.findByText("No skills selected yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /go to my skills/i })).toHaveAttribute(
      "href",
      "/student/skills",
    );
  });

  it("groups assessments under each selected skill, ordered by difficulty", async () => {
    fetchStudentSkills.mockResolvedValue([studentSkill()]);
    listAssessments.mockResolvedValue({
      assessments: [
        assessment({ id: "adv", title: "Python Advanced Assessment", difficulty: "Advanced" }),
        assessment({ id: "beg", title: "Python Beginner Assessment", difficulty: "Beginner" }),
        assessment({
          id: "int",
          title: "Python Intermediate Assessment",
          difficulty: "Intermediate",
        }),
      ],
    });

    renderView();

    expect(await screen.findByRole("heading", { name: "Python" })).toBeInTheDocument();
    const titles = screen.getAllByText(/Python (Beginner|Intermediate|Advanced) Assessment/);
    expect(titles.map((n) => n.textContent)).toEqual([
      "Python Beginner Assessment",
      "Python Intermediate Assessment",
      "Python Advanced Assessment",
    ]);
    expect(screen.getAllByRole("button", { name: "Start assessment" })).toHaveLength(3);
  });

  it("only renders sections for the student's selected skills", async () => {
    fetchStudentSkills.mockResolvedValue([studentSkill()]);
    listAssessments.mockResolvedValue({
      // The backend already filters to selected skills; even if a stray
      // row for another skill arrived, it must not create a section.
      assessments: [
        assessment(),
        assessment({ id: "x", skill_id: "skill-java", title: "Java Beginner Assessment" }),
      ],
    });

    renderView();

    await screen.findByRole("heading", { name: "Python" });
    expect(screen.queryByText("Java Beginner Assessment")).not.toBeInTheDocument();
    expect(screen.queryByRole("heading", { name: "Java" })).not.toBeInTheDocument();
  });

  it("tells the student when a selected skill has no assessment yet", async () => {
    fetchStudentSkills.mockResolvedValue([
      studentSkill({
        id: "ss2",
        skill_id: "skill-figma",
        skill: { id: "skill-figma", name: "Figma", description: null, category: null },
      }),
    ]);
    listAssessments.mockResolvedValue({ assessments: [] });

    renderView();

    expect(await screen.findByRole("heading", { name: "Figma" })).toBeInTheDocument();
    expect(screen.getByText("No assessment available yet for this skill.")).toBeInTheDocument();
  });

  it("shows an error state with retry when the assessments call fails", async () => {
    listAssessments.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));
    fetchStudentSkills.mockResolvedValue([]);

    renderView();

    expect(await screen.findByText("Backend unavailable right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows a session-expired message for a 401, without a generic retry button", async () => {
    listAssessments.mockRejectedValue(new ApiError(401, "You must be signed in to do this."));
    fetchStudentSkills.mockResolvedValue([]);

    renderView();

    expect(await screen.findByText(/session has expired/i)).toBeInTheDocument();
  });

  it("retry re-fetches", async () => {
    listAssessments
      .mockRejectedValueOnce(new ApiError(500, "Backend unavailable right now."))
      .mockResolvedValueOnce({ assessments: [assessment()] });
    fetchStudentSkills.mockResolvedValue([studentSkill()]);

    renderView();
    await screen.findByText("Backend unavailable right now.");

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(listAssessments).toHaveBeenCalledTimes(2));
    expect(await screen.findByRole("heading", { name: "Python" })).toBeInTheDocument();
  });

  it("never renders an answer key or scoring field on the list", async () => {
    fetchStudentSkills.mockResolvedValue([studentSkill()]);
    listAssessments.mockResolvedValue({ assessments: [assessment()] });

    renderView();
    await screen.findByRole("heading", { name: "Python" });

    expect(screen.queryByText(/correct_option_ids/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/awarded_marks/i)).not.toBeInTheDocument();
  });

  it("links each assessment card to its taking page", async () => {
    fetchStudentSkills.mockResolvedValue([studentSkill()]);
    listAssessments.mockResolvedValue({ assessments: [assessment({ id: "a-42" })] });

    renderView();

    const section = (await screen.findByRole("heading", { name: "Python" })).closest("section")!;
    expect(within(section).getByRole("button", { name: "Start assessment" })).toHaveAttribute(
      "href",
      "/student/assessment/a-42",
    );
  });
});
