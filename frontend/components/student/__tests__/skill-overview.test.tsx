import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { SkillOverview } from "@/components/student/skill-overview";
import type { StudentSkill } from "@/lib/student/skills";

function skill(overrides: Partial<StudentSkill> = {}): StudentSkill {
  return {
    id: crypto.randomUUID(),
    skill_id: "s",
    proficiency_level: "Beginner",
    proficiency_score: null,
    is_verified: false,
    created_at: "",
    updated_at: "",
    skill: { id: "s", name: "Python", description: null, category: { id: "c", name: "Programming" } },
    ...overrides,
  } as StudentSkill;
}

describe("SkillOverview", () => {
  it("renders real skill counts, verified count, and the proficiency distribution", () => {
    render(
      <SkillOverview
        studentSkills={[
          skill({ proficiency_level: "Beginner" }),
          skill({ proficiency_level: "Advanced", is_verified: true }),
          skill({ proficiency_level: "Expert", is_verified: true }),
        ]}
      />,
    );
    expect(screen.getByText("3")).toBeInTheDocument(); // total
    expect(screen.getByText("skills tracked")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument(); // verified
    expect(screen.getByText("assessment-verified")).toBeInTheDocument();
    // the proficiency distribution rows are present (also appear as list
    // badges, hence getAllByText — every one of the 4 levels is labelled)
    for (const level of ["Beginner", "Intermediate", "Advanced", "Expert"]) {
      expect(screen.getAllByText(level).length).toBeGreaterThan(0);
    }
    // 3 progress bars for the non-zero-capable distribution
    expect(screen.getAllByRole("progressbar").length).toBe(4);
  });

  it("does not render a demo radar / fabricated skill score", () => {
    const { container } = render(<SkillOverview studentSkills={[skill()]} />);
    expect(screen.queryByText(/demo data/i)).not.toBeInTheDocument();
    expect(screen.queryByText(/skill score/i)).not.toBeInTheDocument();
    expect(container.textContent).not.toContain("Problem Solving"); // former MOCK_SKILL_RADAR category
    expect(container.querySelector(".recharts-wrapper")).toBeNull();
  });

  it("shows an add-skills empty state for a student with no skills", () => {
    const { container } = render(<SkillOverview studentSkills={[]} />);
    expect(screen.getByText("No skills added yet.")).toBeInTheDocument();
    expect(container.querySelector('a[href="/student/skills"]')).not.toBeNull();
  });
});
