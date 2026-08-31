import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { SkillOverview } from "@/components/student/skill-overview";
import type { StudentSkill } from "@/lib/student/skills";

function skill(overrides: Partial<StudentSkill> = {}): StudentSkill {
  return {
    id: "s1",
    proficiency_level: "Intermediate",
    skill: { id: "sk1", name: "Python", category: { id: "c1", name: "Programming" } },
    ...overrides,
  } as StudentSkill;
}

describe("SkillOverview", () => {
  it("always renders the Take an Assessment CTA, pointing at the real assessment route", () => {
    render(<SkillOverview radar={[]} studentSkills={[skill()]} />);
    const cta = screen.getByRole("button", { name: "Take an Assessment" });
    expect(cta).toHaveAttribute("href", "/student/assessment");
  });

  it("still renders the CTA when there are no self-reported skills yet", () => {
    render(<SkillOverview radar={[]} studentSkills={[]} />);
    expect(screen.getByRole("button", { name: "Take an Assessment" })).toHaveAttribute(
      "href",
      "/student/assessment",
    );
  });

  it("keeps the existing View All link pointing at the skills page", () => {
    render(<SkillOverview radar={[]} studentSkills={[skill()]} />);
    expect(screen.getByRole("button", { name: "View All" })).toHaveAttribute("href", "/student/skills");
  });
});
