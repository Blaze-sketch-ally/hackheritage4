import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listAssessmentsForFaculty, getBlueprint, replaceBlueprint } = vi.hoisted(() => ({
  listAssessmentsForFaculty: vi.fn(),
  getBlueprint: vi.fn(),
  replaceBlueprint: vi.fn(),
}));

vi.mock("@/lib/faculty/question-bank", () => ({
  listAssessmentsForFaculty,
  getBlueprint,
  replaceBlueprint,
}));

import { BlueprintEditor } from "@/components/faculty/blueprint-editor";
import { ApiError } from "@/lib/api";

const assessment = {
  id: "a1",
  skill_id: "skill-1",
  title: "Python Fundamentals",
  description: null,
  difficulty: "Beginner",
  duration_minutes: 15,
  question_count: null,
  is_active: true,
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

describe("BlueprintEditor", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads the existing blueprint for the first assessment and pre-fills counts", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    getBlueprint.mockResolvedValue({
      assessment_id: "a1",
      rules: [
        { id: "r1", assessment_id: "a1", difficulty: "Beginner", question_count: 8, created_at: "", updated_at: "" },
      ],
    });

    render(<BlueprintEditor />);

    await waitFor(() => expect(getBlueprint).toHaveBeenCalledWith("a1"));
    expect(await screen.findByDisplayValue("8")).toBeInTheDocument();
    expect(await screen.findByText(/total: 8 questions per attempt/i)).toBeInTheDocument();
  });

  it("saves only the difficulties with a count greater than zero", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    getBlueprint.mockResolvedValue({ assessment_id: "a1", rules: [] });
    replaceBlueprint.mockResolvedValue({ assessment_id: "a1", rules: [] });

    render(<BlueprintEditor />);
    await waitFor(() => expect(getBlueprint).toHaveBeenCalled());

    await userEvent.type(screen.getByLabelText("Beginner"), "8");
    await userEvent.type(screen.getByLabelText("Advanced"), "5");

    await userEvent.click(screen.getByRole("button", { name: /save blueprint/i }));

    await waitFor(() =>
      expect(replaceBlueprint).toHaveBeenCalledWith("a1", [
        { difficulty: "Beginner", question_count: 8 },
        { difficulty: "Advanced", question_count: 5 },
      ]),
    );
    expect(await screen.findByText(/blueprint saved/i)).toBeInTheDocument();
  });

  it("disables saving when the total is zero", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    getBlueprint.mockResolvedValue({ assessment_id: "a1", rules: [] });

    render(<BlueprintEditor />);
    await waitFor(() => expect(getBlueprint).toHaveBeenCalled());

    expect(screen.getByRole("button", { name: /save blueprint/i })).toBeDisabled();
  });

  it("surfaces a save error without crashing", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    getBlueprint.mockResolvedValue({ assessment_id: "a1", rules: [] });
    replaceBlueprint.mockRejectedValue(new ApiError(403, "You are not allowed to make this change."));

    render(<BlueprintEditor />);
    await waitFor(() => expect(getBlueprint).toHaveBeenCalled());

    await userEvent.type(screen.getByLabelText("Beginner"), "8");
    await userEvent.click(screen.getByRole("button", { name: /save blueprint/i }));

    expect(await screen.findByText("You are not allowed to make this change.")).toBeInTheDocument();
  });
});
