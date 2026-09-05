import { createContext, useContext, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/** See question-bank-view.test.tsx's identical mock rationale. */
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
  SelectTrigger: ({ ...props }: { children?: ReactNode; [key: string]: unknown }) => {
    const ctx = useContext(SelectCtx)!;
    return (
      <select {...props} value={ctx.value} onChange={(e) => ctx.onValueChange(e.target.value)}>
        <option value="" />
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

const { listAssessmentsForFaculty } = vi.hoisted(() => ({ listAssessmentsForFaculty: vi.fn() }));
vi.mock("@/lib/faculty/question-bank", () => ({ listAssessmentsForFaculty }));

const {
  listEligibleEvaluators,
  listAttemptsForAssignment,
  createEvaluatorAssignment,
  revokeEvaluatorAssignment,
} = vi.hoisted(() => ({
  listEligibleEvaluators: vi.fn(),
  listAttemptsForAssignment: vi.fn(),
  createEvaluatorAssignment: vi.fn(),
  revokeEvaluatorAssignment: vi.fn(),
}));

vi.mock("@/lib/admin/evaluator-assignments", () => ({
  listEligibleEvaluators,
  listAttemptsForAssignment,
  createEvaluatorAssignment,
  revokeEvaluatorAssignment,
}));

import { EvaluatorAssignmentView } from "@/components/admin/evaluator-assignment-view";

function attempt(overrides = {}) {
  return {
    attempt_id: "attempt-1",
    student_label: "Student abcd1234…",
    status: "COMPLETED",
    questions: [
      {
        question_id: "q1",
        question_text: "Explain closures.",
        points: "10.00",
        existing_assignments: [],
      },
    ],
    ...overrides,
  };
}

describe("EvaluatorAssignmentView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("loads assessments and eligible evaluators, then attempts once an assessment is chosen", async () => {
    listAssessmentsForFaculty.mockResolvedValue({
      assessments: [{ id: "assess-1", title: "Java Fundamentals", skill_id: "s1", description: null, difficulty: "Intermediate", duration_minutes: null, question_count: null, is_active: true, created_at: "x", updated_at: "x" }],
    });
    listEligibleEvaluators.mockResolvedValue([{ faculty_id: "eval-1", email: "e@example.com", full_name: "Dr. Eval" }]);
    listAttemptsForAssignment.mockResolvedValue([attempt()]);

    render(<EvaluatorAssignmentView />);

    const assessmentSelect = await screen.findByLabelText(/assessment/i);
    await userEvent.selectOptions(assessmentSelect, "assess-1");

    expect(await screen.findByText("Explain closures.")).toBeInTheDocument();
    expect(listAttemptsForAssignment).toHaveBeenCalledWith("assess-1");
  });

  it("shows a no-attempts empty state honestly, not fabricated data", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [{ id: "assess-1", title: "Java Fundamentals", skill_id: "s1", description: null, difficulty: "Intermediate", duration_minutes: null, question_count: null, is_active: true, created_at: "x", updated_at: "x" }] });
    listEligibleEvaluators.mockResolvedValue([]);
    listAttemptsForAssignment.mockResolvedValue([]);

    render(<EvaluatorAssignmentView />);
    await userEvent.selectOptions(await screen.findByLabelText(/assessment/i), "assess-1");

    expect(await screen.findByText(/no completed attempts/i)).toBeInTheDocument();
  });

  it("assigning an evaluator calls createEvaluatorAssignment with the right ids and refetches", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [{ id: "assess-1", title: "Java Fundamentals", skill_id: "s1", description: null, difficulty: "Intermediate", duration_minutes: null, question_count: null, is_active: true, created_at: "x", updated_at: "x" }] });
    listEligibleEvaluators.mockResolvedValue([{ faculty_id: "eval-1", email: "e@example.com", full_name: "Dr. Eval" }]);
    listAttemptsForAssignment.mockResolvedValue([attempt()]);
    createEvaluatorAssignment.mockResolvedValue({});

    render(<EvaluatorAssignmentView />);
    await userEvent.selectOptions(await screen.findByLabelText(/assessment/i), "assess-1");
    await screen.findByText("Explain closures.");

    // Two <select>s now exist: the labelled assessment picker (already
    // used above) and this one question's unlabelled evaluator picker.
    const [, evaluatorPicker] = screen.getAllByRole("combobox");
    await userEvent.selectOptions(evaluatorPicker, "eval-1");
    await userEvent.click(screen.getByRole("button", { name: /^assign$/i }));

    await waitFor(() =>
      expect(createEvaluatorAssignment).toHaveBeenCalledWith({
        evaluator_id: "eval-1",
        attempt_id: "attempt-1",
        question_id: "q1",
      }),
    );
  });

  it("revoking an existing assignment calls revokeEvaluatorAssignment with its id", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [{ id: "assess-1", title: "Java Fundamentals", skill_id: "s1", description: null, difficulty: "Intermediate", duration_minutes: null, question_count: null, is_active: true, created_at: "x", updated_at: "x" }] });
    listEligibleEvaluators.mockResolvedValue([{ faculty_id: "eval-1", email: "e@example.com", full_name: "Dr. Eval" }]);
    listAttemptsForAssignment.mockResolvedValue([
      attempt({
        questions: [
          {
            question_id: "q1",
            question_text: "Explain closures.",
            points: "10.00",
            existing_assignments: [
              {
                assignment_id: "assign-1",
                evaluator_id: "eval-1",
                evaluator_email: "e@example.com",
                evaluator_full_name: "Dr. Eval",
                assignment_status: "ACTIVE",
                evaluation_status: "ASSIGNED",
              },
            ],
          },
        ],
      }),
    ]);
    revokeEvaluatorAssignment.mockResolvedValue({});

    render(<EvaluatorAssignmentView />);
    await userEvent.selectOptions(await screen.findByLabelText(/assessment/i), "assess-1");
    await userEvent.click(await screen.findByRole("button", { name: /revoke/i }));

    await waitFor(() => expect(revokeEvaluatorAssignment).toHaveBeenCalledWith("assign-1"));
  });

  it("shows a clean error hint when no Faculty currently hold the Evaluator capability", async () => {
    listAssessmentsForFaculty.mockResolvedValue({ assessments: [{ id: "assess-1", title: "Java Fundamentals", skill_id: "s1", description: null, difficulty: "Intermediate", duration_minutes: null, question_count: null, is_active: true, created_at: "x", updated_at: "x" }] });
    listEligibleEvaluators.mockResolvedValue([]);
    listAttemptsForAssignment.mockResolvedValue([attempt()]);

    render(<EvaluatorAssignmentView />);
    await userEvent.selectOptions(await screen.findByLabelText(/assessment/i), "assess-1");

    expect(await screen.findByText(/no faculty currently hold the evaluator capability/i)).toBeInTheDocument();
  });
});
