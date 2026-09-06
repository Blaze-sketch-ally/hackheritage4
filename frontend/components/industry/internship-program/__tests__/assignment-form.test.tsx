import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { AssignmentForm } from "@/components/industry/internship-program/assignment-form";
import type { ProgramSkill } from "@/types/internship-program";

const SKILLS: ProgramSkill[] = [
  { skill_id: "sk-py", skill_name: "Python", requirement: "REQUIRED" },
];

describe("AssignmentForm", () => {
  it("submits a normalized payload with server-safe defaults", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <AssignmentForm programSkills={SKILLS} busy={false} onSubmit={onSubmit} onCancel={vi.fn()} />,
    );

    await user.type(screen.getByLabelText(/assignment title/i), "Build a CLI");
    await user.click(screen.getByRole("button", { name: /add assignment/i }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({
        title: "Build a CLI",
        assignment_type: "ASSIGNMENT",
        submission_kind: "LINK",
        repo_required: false,
        live_url_expected: false,
        is_required: true,
        due_offset_days: null,
        max_score: null,
        linked_skill_id: null,
      }),
    );
  });

  it("forces a REPO/MIXED kind when 'requires a repository' is checked", async () => {
    const user = userEvent.setup();
    const onSubmit = vi.fn().mockResolvedValue(undefined);
    render(
      <AssignmentForm programSkills={SKILLS} busy={false} onSubmit={onSubmit} onCancel={vi.fn()} />,
    );

    await user.type(screen.getByLabelText(/assignment title/i), "Repo task");
    await user.click(screen.getByLabelText(/requires a code repository/i));
    await user.click(screen.getByRole("button", { name: /add assignment/i }));

    expect(onSubmit).toHaveBeenCalledWith(
      expect.objectContaining({ repo_required: true, submission_kind: "REPO" }),
    );
  });

  it("requires a title", async () => {
    render(
      <AssignmentForm programSkills={SKILLS} busy={false} onSubmit={vi.fn()} onCancel={vi.fn()} />,
    );
    expect(screen.getByRole("button", { name: /add assignment/i })).toBeDisabled();
  });
});
