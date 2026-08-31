import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";

import { StudentSkillsView } from "@/components/student/skills/student-skills-view";

describe("StudentSkillsView CTA", () => {
  it("always renders the Take an Assessment CTA, pointing at the real assessment route", () => {
    render(
      <StudentSkillsView studentId="student-1" initialStudentSkills={[]} catalogSkills={[]} categories={[]} />,
    );
    expect(screen.getByText("Want a verified skill score?")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Take an Assessment" })).toHaveAttribute(
      "href",
      "/student/assessment",
    );
  });
});
