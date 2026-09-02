import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

import { EditSkillDialog } from "@/components/student/skills/edit-skill-dialog";
import type { StudentSkill } from "@/lib/student/skills";

function studentSkill(overrides: Partial<StudentSkill> = {}): StudentSkill {
  return {
    id: "ss-1",
    skill_id: "skill-1",
    proficiency_level: "Intermediate",
    proficiency_score: null,
    is_verified: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    skill: { id: "skill-1", name: "Python", description: null, category: null },
    ...overrides,
  };
}

const noop = () => {};

describe("EditSkillDialog", () => {
  it("renders the proficiency editor for the given skill", () => {
    render(
      <EditSkillDialog
        studentSkill={studentSkill()}
        onOpenChange={noop}
        submitting={false}
        error={null}
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByText("Edit Proficiency")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("does not warn about verification loss for an unverified skill", () => {
    render(
      <EditSkillDialog
        studentSkill={studentSkill({ is_verified: false })}
        onOpenChange={noop}
        submitting={false}
        error={null}
        onSave={vi.fn()}
      />,
    );
    expect(screen.queryByText(/assessment-verified/i)).not.toBeInTheDocument();
  });

  it("warns that editing a verified skill removes its verification", () => {
    render(
      <EditSkillDialog
        studentSkill={studentSkill({ is_verified: true, proficiency_level: "Advanced" })}
        onOpenChange={noop}
        submitting={false}
        error={null}
        onSave={vi.fn()}
      />,
    );
    expect(screen.getByRole("status")).toHaveTextContent(/assessment-verified at Advanced/i);
    expect(screen.getByRole("status")).toHaveTextContent(/remove that verification/i);
  });
});
