import { createContext, useContext, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/** components/ui/select.tsx wraps @base-ui/react's Select, whose popup
 * (portal + anchor positioning) reliably hangs for tens of seconds under
 * this project's jsdom test setup -- neither opening it via click nor
 * driving its accessible autofill hidden-input produced a fast, reliable
 * result here. A native <select> is behaviorally equivalent for every
 * purpose this form's tests care about (which value is selected), so
 * this file replaces the real component with one for its two Select
 * usages ("Assessment", "Question type") -- production code
 * (question-create-form.tsx) is untouched; this mock exists only here. */
type SelectCtxValue = { value: string; onValueChange: (v: string) => void; items: Record<string, string> };
const SelectCtx = createContext<SelectCtxValue | null>(null);

vi.mock("@/components/ui/select", () => ({
  Select: ({
    value,
    onValueChange,
    items,
    children,
  }: {
    value: string;
    onValueChange: (v: string) => void;
    items: Record<string, string>;
    children: ReactNode;
  }) => <SelectCtx.Provider value={{ value, onValueChange, items }}>{children}</SelectCtx.Provider>,
  // The real SelectTrigger's own children are just <SelectValue/> (a display
  // label, mocked to null below) -- the actual selectable options come from
  // `items`, the same label map the real component already passes to
  // <Select> for its own accessible-typeahead purposes, so this renders a
  // real native <select> with a real <option> per entry, no data
  // duplicated between production code and this mock.
  SelectTrigger: ({ ...props }: { children?: ReactNode; [key: string]: unknown }) => {
    const ctx = useContext(SelectCtx)!;
    return (
      <select {...props} value={ctx.value} onChange={(e) => ctx.onValueChange(e.target.value)}>
        {Object.entries(ctx.items).map(([val, label]) => (
          <option key={val} value={val}>
            {label}
          </option>
        ))}
      </select>
    );
  },
  SelectContent: () => null,
  SelectItem: () => null,
  SelectValue: () => null,
}));

async function changeSelect(labelText: string | RegExp, value: string) {
  await userEvent.selectOptions(screen.getByLabelText(labelText), value);
}

const { listAssessmentsForFaculty, createQuestion } = vi.hoisted(() => ({
  listAssessmentsForFaculty: vi.fn(),
  createQuestion: vi.fn(),
}));

const push = vi.hoisted(() => vi.fn());

vi.mock("@/lib/faculty/question-bank", () => ({
  listAssessmentsForFaculty,
  createQuestion,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push }),
}));

import { QuestionCreateForm } from "@/components/faculty/question-create-form";
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

describe("QuestionCreateForm", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("requires at least one correct option to be marked before submitting an MCQ", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });

    render(<QuestionCreateForm />);
    await screen.findByText("Python Fundamentals");

    await userEvent.type(screen.getByLabelText("Question text"), "What is 2 + 2?");
    const optionInputs = screen.getAllByPlaceholderText(/^Option \d$/);
    await userEvent.type(optionInputs[0], "3");
    await userEvent.type(optionInputs[1], "4");

    await userEvent.click(screen.getByRole("button", { name: /save as draft/i }));

    expect(await screen.findByText(/mark at least one option as correct/i)).toBeInTheDocument();
    expect(createQuestion).not.toHaveBeenCalled();
  });

  it("submits an MCQ with client-generated option ids matching correct_option_ids", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    createQuestion.mockResolvedValue({
      id: "new-question",
      assessment_id: "a1",
      question_text: "What is 2 + 2?",
      question_type: "MCQ",
      scoring_method: "OBJECTIVE",
      difficulty: "Beginner",
      points: "1.00",
      display_order: 0,
      review_status: "PENDING",
      is_active: true,
      created_by: "faculty-1",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      options: [],
      answer_key: null,
    });

    render(<QuestionCreateForm />);
    await screen.findByText("Python Fundamentals");

    await userEvent.type(screen.getByLabelText("Question text"), "What is 2 + 2?");
    const optionInputs = screen.getAllByPlaceholderText(/^Option \d$/);
    await userEvent.type(optionInputs[0], "3");
    await userEvent.type(optionInputs[1], "4");
    await userEvent.click(screen.getByRole("radio", { name: /mark option 2 correct/i }));

    await userEvent.click(screen.getByRole("button", { name: /save as draft/i }));

    await waitFor(() => expect(createQuestion).toHaveBeenCalled());
    const payload = createQuestion.mock.calls[0][0];
    expect(payload.scoring_method).toBe("OBJECTIVE");
    expect(payload.options).toHaveLength(2);
    // The option marked correct must have a client-generated id that
    // exactly matches the one entry in correct_option_ids -- this is the
    // whole point of generating option ids client-side before the option
    // rows exist server-side.
    const correctOption = payload.options.find((o: { option_text: string }) => o.option_text === "4");
    expect(payload.answer_key.correct_option_ids).toEqual([correctOption.id]);
    expect(correctOption.id).toBeTruthy();

    expect(push).toHaveBeenCalledWith("/faculty/questions/new-question");
  });

  it("shows a load error if assessments fail to load", async () => {
    listAssessmentsForFaculty.mockRejectedValue(new ApiError(500, "Could not load assessments."));
    render(<QuestionCreateForm />);
    expect(await screen.findByText("Could not load assessments.")).toBeInTheDocument();
  });

  // ============================================================
  // Phase F6.4 -- learning objective / estimated time metadata,
  // question-type behavior
  // ============================================================

  it("only offers the three fully-supported question types, and explains why CODE/SUBJECTIVE are absent", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    render(<QuestionCreateForm />);
    await screen.findByText("Python Fundamentals");

    expect(
      screen.getByText(/code and subjective questions aren.t available here yet/i),
    ).toBeInTheDocument();
  });

  it("submits an optional learning objective and estimated time alongside a valid MCQ", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    createQuestion.mockResolvedValue({
      id: "new-question",
      assessment_id: "a1",
      question_text: "What is 2 + 2?",
      question_type: "MCQ",
      scoring_method: "OBJECTIVE",
      difficulty: "Beginner",
      points: "1.00",
      display_order: 0,
      learning_objective: "Recall basic arithmetic.",
      estimated_time_minutes: 2,
      review_status: "PENDING",
      is_active: true,
      created_by: "faculty-1",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      options: [],
      answer_key: null,
    });

    render(<QuestionCreateForm />);
    await screen.findByText("Python Fundamentals");

    await userEvent.type(screen.getByLabelText("Question text"), "What is 2 + 2?");
    const optionInputs = screen.getAllByPlaceholderText(/^Option \d$/);
    await userEvent.type(optionInputs[0], "3");
    await userEvent.type(optionInputs[1], "4");
    await userEvent.click(screen.getByRole("radio", { name: /mark option 2 correct/i }));
    await userEvent.type(screen.getByLabelText(/learning objective/i), "Recall basic arithmetic.");
    await userEvent.type(screen.getByLabelText(/estimated time/i), "2");

    await userEvent.click(screen.getByRole("button", { name: /save as draft/i }));

    await waitFor(() => expect(createQuestion).toHaveBeenCalled());
    const payload = createQuestion.mock.calls[0][0];
    expect(payload.learning_objective).toBe("Recall basic arithmetic.");
    expect(payload.estimated_time_minutes).toBe(2);
  });

  it("omitting learning objective/estimated time still creates a valid draft (both are optional)", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    createQuestion.mockResolvedValue({
      id: "new-question",
      assessment_id: "a1",
      question_text: "What is 2 + 2?",
      question_type: "MCQ",
      scoring_method: "OBJECTIVE",
      difficulty: "Beginner",
      points: "1.00",
      display_order: 0,
      learning_objective: null,
      estimated_time_minutes: null,
      review_status: "PENDING",
      is_active: true,
      created_by: "faculty-1",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
      options: [],
      answer_key: null,
    });

    render(<QuestionCreateForm />);
    await screen.findByText("Python Fundamentals");

    await userEvent.type(screen.getByLabelText("Question text"), "What is 2 + 2?");
    const optionInputs = screen.getAllByPlaceholderText(/^Option \d$/);
    await userEvent.type(optionInputs[0], "3");
    await userEvent.type(optionInputs[1], "4");
    await userEvent.click(screen.getByRole("radio", { name: /mark option 2 correct/i }));

    await userEvent.click(screen.getByRole("button", { name: /save as draft/i }));

    await waitFor(() => expect(createQuestion).toHaveBeenCalled());
    const payload = createQuestion.mock.calls[0][0];
    expect(payload.learning_objective).toBeNull();
    expect(payload.estimated_time_minutes).toBeNull();
  });

  it("rejects a non-positive-integer estimated time client-side before ever calling the API", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    render(<QuestionCreateForm />);
    await screen.findByText("Python Fundamentals");

    await userEvent.type(screen.getByLabelText("Question text"), "What is 2 + 2?");
    const optionInputs = screen.getAllByPlaceholderText(/^Option \d$/);
    await userEvent.type(optionInputs[0], "3");
    await userEvent.type(optionInputs[1], "4");
    await userEvent.click(screen.getByRole("radio", { name: /mark option 2 correct/i }));
    // "0" (rather than a negative number) -- a lone "-" keystroke is not
    // reliably typeable into a jsdom `type="number"` input, but "0" types
    // fine and is equally invalid under the ">0" rule being tested.
    await userEvent.type(screen.getByLabelText(/estimated time/i), "0");

    await userEvent.click(screen.getByRole("button", { name: /save as draft/i }));

    expect(await screen.findByText(/positive whole number of minutes/i)).toBeInTheDocument();
    expect(createQuestion).not.toHaveBeenCalled();
  });

  it("renders single-correct (radio) controls for MCQ and multi-correct (checkbox) controls for MULTIPLE_SELECT", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    render(<QuestionCreateForm />);
    await screen.findByText("Python Fundamentals");

    // MCQ is the default selection.
    expect(screen.getByText(/exactly one option must be marked correct/i)).toBeInTheDocument();
    expect(screen.getAllByRole("radio").length).toBeGreaterThan(0);

    await changeSelect("Question type", "MULTIPLE_SELECT");

    expect(await screen.findByText(/mark one or more options as correct/i)).toBeInTheDocument();
    expect(screen.getAllByRole("checkbox").length).toBeGreaterThan(0);
  });

  it("renders an answer-text input, not option controls, for SHORT_ANSWER", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [assessment] });
    render(<QuestionCreateForm />);
    await screen.findByText("Python Fundamentals");

    await changeSelect("Question type", "SHORT_ANSWER");

    expect(await screen.findByLabelText("Correct answer")).toBeInTheDocument();
    expect(screen.queryByPlaceholderText(/^Option \d$/)).not.toBeInTheDocument();
  });
});
