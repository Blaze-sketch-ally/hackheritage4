import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SkillCard } from "@/components/student/skill-card";
import type { StudentSkill } from "@/lib/student/skills";
import type { Assessment } from "@/types/assessment";

function studentSkill(overrides: Partial<StudentSkill> = {}): StudentSkill {
  return {
    id: "student-skill-1",
    skill_id: "skill-python",
    proficiency_level: "Advanced",
    proficiency_score: null,
    is_verified: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    skill: { id: "skill-python", name: "Python", description: null, category: { id: "cat-1", name: "Languages" } },
    ...overrides,
  };
}

function assessment(overrides: Partial<Assessment> = {}): Assessment {
  return {
    id: "assessment-1",
    skill_id: "skill-python",
    title: "Python Advanced Assessment",
    description: null,
    difficulty: "Advanced",
    duration_minutes: 20,
    question_count: 15,
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("SkillCard", () => {
  it("shows 'Assessment not available yet.' when no matching assessment exists", () => {
    render(<SkillCard studentSkill={studentSkill()} onEdit={vi.fn()} onDelete={vi.fn()} />);

    expect(screen.getByText("Assessment not available yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /take .* assessment/i })).not.toBeInTheDocument();
  });

  it("links to the matching assessment with the declared level in the label when not verified", () => {
    render(
      <SkillCard
        studentSkill={studentSkill({ is_verified: false })}
        matchingAssessment={assessment()}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    const link = screen.getByRole("button", { name: "Take Advanced Assessment" });
    expect(link).toHaveAttribute("href", "/student/assessment/assessment-1");
  });

  it("shows a generic 'Take Assessment' label once already verified", () => {
    render(
      <SkillCard
        studentSkill={studentSkill({ is_verified: true })}
        matchingAssessment={assessment()}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getByRole("button", { name: "Take Assessment" })).toBeInTheDocument();
    expect(screen.getByText("Verified")).toBeInTheDocument();
  });

  it("never shows a Take Assessment link for a different skill or level than declared", () => {
    // matchingAssessment intentionally omitted -- the parent component
    // (student-skills-view.tsx) is responsible for exact (skill_id,
    // proficiency_level) matching before ever passing one in; this test
    // guards the card's own fallback behavior when nothing matched.
    render(
      <SkillCard studentSkill={studentSkill({ proficiency_level: "Beginner" })} onEdit={vi.fn()} onDelete={vi.fn()} />,
    );

    expect(screen.getByText("Assessment not available yet.")).toBeInTheDocument();
  });
});
