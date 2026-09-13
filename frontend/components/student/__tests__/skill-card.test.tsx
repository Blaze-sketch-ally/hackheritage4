import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { SkillCard } from "@/components/student/skill-card";
import type { StudentSkill } from "@/lib/student/skills";
import type { Assessment, AttemptHistoryItem } from "@/types/assessment";

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
    passing_percentage: "70.00",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function attempt(overrides: Partial<AttemptHistoryItem> = {}): AttemptHistoryItem {
  return {
    id: "attempt-1",
    status: "COMPLETED",
    started_at: "2026-01-01T00:00:00Z",
    submitted_at: "2026-01-01T00:10:00Z",
    score: "40.00",
    total_marks: "100.00",
    percentage: "40.00",
    passed: false,
    skill_verified: false,
    assessment: assessment(),
    ...overrides,
  };
}

describe("SkillCard", () => {
  it("shows 'Assessment not available yet.' when no matching assessment exists", () => {
    render(<SkillCard studentSkill={studentSkill()} onEdit={vi.fn()} onDelete={vi.fn()} />);

    expect(screen.getByText("Assessment not available yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /verify skill/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /take .* assessment/i })).not.toBeInTheDocument();
  });

  it("shows a 'Verify Skill' action (not the old 'Take {Level} Assessment' wording) linking to the matching assessment when not verified", () => {
    render(
      <SkillCard
        studentSkill={studentSkill({ is_verified: false })}
        matchingAssessment={assessment()}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    const link = screen.getByRole("button", { name: "Verify Skill" });
    expect(link).toHaveAttribute("href", "/student/assessment/assessment-1");
    expect(screen.getByText("Pass the assessment to verify this skill.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /take .* assessment/i })).not.toBeInTheDocument();
    expect(screen.queryByText(/^Take /)).not.toBeInTheDocument();
  });

  it("shows a 'View Assessment' action once already verified", () => {
    render(
      <SkillCard
        studentSkill={studentSkill({ is_verified: true })}
        matchingAssessment={assessment()}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    const link = screen.getByRole("button", { name: "View Assessment" });
    expect(link).toHaveAttribute("href", "/student/assessment/assessment-1");
    expect(screen.getByText("Verified")).toBeInTheDocument();
  });

  it("never shows a Verify Skill link for a different skill or level than declared", () => {
    // matchingAssessment intentionally omitted -- the parent component
    // (student-skills-view.tsx) is responsible for exact (skill_id,
    // proficiency_level) matching before ever passing one in; this test
    // guards the card's own fallback behavior when nothing matched.
    render(
      <SkillCard studentSkill={studentSkill({ proficiency_level: "Beginner" })} onEdit={vi.fn()} onDelete={vi.fn()} />,
    );

    expect(screen.getByText("Assessment not available yet.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /verify skill/i })).not.toBeInTheDocument();
  });

  it("shows a disabled, accessible loading action while the lookup is in flight instead of claiming no assessment exists", () => {
    render(
      <SkillCard
        studentSkill={studentSkill()}
        lookupStatus="loading"
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.queryByText("Assessment not available yet.")).not.toBeInTheDocument();
    const button = screen.getByRole("button", { name: "Checking assessment availability" });
    expect(button).toBeDisabled();
  });

  it("shows an honest error state when the lookup fails, instead of claiming no assessment exists", () => {
    render(
      <SkillCard studentSkill={studentSkill()} lookupStatus="error" onEdit={vi.fn()} onDelete={vi.fn()} />,
    );

    expect(screen.queryByText("Assessment not available yet.")).not.toBeInTheDocument();
    expect(screen.getByText(/Couldn't check assessment status/)).toBeInTheDocument();
  });

  it("shows a Resume Assessment action when the student has an in-progress attempt", () => {
    render(
      <SkillCard
        studentSkill={studentSkill({ is_verified: false })}
        matchingAssessment={assessment()}
        latestAttempt={attempt({ status: "IN_PROGRESS", passed: null, skill_verified: null })}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getByText("Attempt in progress")).toBeInTheDocument();
    const link = screen.getByRole("button", { name: "Resume Assessment" });
    expect(link).toHaveAttribute("href", "/student/assessment/assessment-1");
  });

  it("shows a Retake Assessment action and the last outcome when the most recent attempt failed", () => {
    render(
      <SkillCard
        studentSkill={studentSkill({ is_verified: false })}
        matchingAssessment={assessment()}
        latestAttempt={attempt({ status: "COMPLETED", passed: false })}
        onEdit={vi.fn()}
        onDelete={vi.fn()}
      />,
    );

    expect(screen.getByText("Last attempt: Failed")).toBeInTheDocument();
    const link = screen.getByRole("button", { name: "Retake Assessment" });
    expect(link).toHaveAttribute("href", "/student/assessment/assessment-1");
  });
});
