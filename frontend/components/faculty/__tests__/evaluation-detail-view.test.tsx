import { cloneElement, isValidElement, type ReactElement, type ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

/** See question-bank-view.test.tsx's identical mock rationale for
 * Select: the real @base-ui/react primitives this project's dialog.tsx
 * wraps reliably hang for tens of seconds under this project's jsdom
 * test setup. This mock always renders Dialog content inline (no real
 * open/close/portal/focus-trap state) -- behaviorally sufficient for
 * what these tests check (clicking the trigger/confirm/cancel buttons),
 * not a claim that the real dialog's visual behavior is tested here.
 * Production code (evaluation-detail-view.tsx) is untouched; this mock
 * exists only in this test file. */
function passthrough({ render: renderProp, children }: { render?: ReactElement; children?: ReactNode }) {
  if (renderProp && isValidElement(renderProp)) {
    return cloneElement(renderProp, undefined, children);
  }
  return <>{children}</>;
}

vi.mock("@/components/ui/dialog", () => ({
  Dialog: ({ children }: { children: ReactNode }) => <>{children}</>,
  DialogTrigger: passthrough,
  DialogContent: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogHeader: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogFooter: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogTitle: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogDescription: ({ children }: { children: ReactNode }) => <div>{children}</div>,
  DialogClose: passthrough,
}));

/** Same rationale, same file-scoped-only mock, for Select. */
import { createContext, useContext } from "react";
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

const { getEvaluation, listCandidateRubrics, saveEvaluation, updateEvaluationStatus } = vi.hoisted(() => ({
  getEvaluation: vi.fn(),
  listCandidateRubrics: vi.fn(),
  saveEvaluation: vi.fn(),
  updateEvaluationStatus: vi.fn(),
}));

vi.mock("@/lib/faculty/evaluations", () => ({
  getEvaluation,
  listCandidateRubrics,
  saveEvaluation,
  updateEvaluationStatus,
}));

import { EvaluationDetailView } from "@/components/faculty/evaluation-detail-view";
import { ApiError } from "@/lib/api";

function detail(overrides = {}) {
  return {
    evaluation_id: "e1",
    assignment_id: "a1",
    status: "ASSIGNED",
    awarded_marks: null,
    feedback: null,
    rubric_id: null,
    submitted_at: null,
    finalized_at: null,
    finalized_by: null,
    attempt_id: "attempt-1",
    question_id: "q1",
    student_id: "student-1",
    assessment_title: "Java Fundamentals",
    assigned_at: "2026-01-01T00:00:00Z",
    question: {
      id: "q1",
      assessment_id: "assess-1",
      question_text: "Explain closures.",
      question_type: "SUBJECTIVE",
      scoring_method: "AI_EVALUATED",
      difficulty: "Intermediate",
      points: "10.00",
      display_order: 0,
      options: [],
    },
    student_answer: { id: "ans-1", attempt_id: "attempt-1", question_id: "q1", answer_text: "A closure captures scope.", selected_option_ids: null, awarded_marks: null, is_correct: null, created_at: "x", updated_at: "x" },
    rubric: null,
    ...overrides,
  };
}

function rubric(overrides = {}) {
  return {
    id: "rubric-1",
    question_id: "q1",
    name: "Correctness",
    description: null,
    max_marks: "10.00",
    status: "ACTIVE",
    criteria: [{ id: "c1", rubric_id: "rubric-1", criterion: "Accuracy", description: null, max_marks: "10.00", display_order: 0 }],
    ...overrides,
  };
}

describe("EvaluationDetailView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the question, student answer, and a Start Evaluation action while ASSIGNED", async () => {
    getEvaluation.mockResolvedValue(detail());
    listCandidateRubrics.mockResolvedValue([rubric()]);

    render(<EvaluationDetailView evaluationId="e1" />);

    expect(await screen.findByText("Explain closures.")).toBeInTheDocument();
    expect(screen.getByText("A closure captures scope.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /start evaluation/i })).toBeInTheDocument();
    // No rubric form yet -- ASSIGNED shows a prompt, not the editable form.
    expect(screen.queryByLabelText(/choose a rubric/i)).not.toBeInTheDocument();
  });

  it("starting the evaluation calls the status endpoint and reloads", async () => {
    getEvaluation.mockResolvedValueOnce(detail()).mockResolvedValueOnce(detail({ status: "IN_PROGRESS" }));
    listCandidateRubrics.mockResolvedValue([rubric()]);
    updateEvaluationStatus.mockResolvedValue({});

    render(<EvaluationDetailView evaluationId="e1" />);
    await userEvent.click(await screen.findByRole("button", { name: /start evaluation/i }));

    await waitFor(() => expect(updateEvaluationStatus).toHaveBeenCalledWith("e1", "IN_PROGRESS"));
    expect(await screen.findByLabelText(/choose a rubric/i)).toBeInTheDocument();
  });

  it("shows the rubric picker, marks, and feedback fields while IN_PROGRESS", async () => {
    getEvaluation.mockResolvedValue(detail({ status: "IN_PROGRESS" }));
    listCandidateRubrics.mockResolvedValue([rubric()]);

    render(<EvaluationDetailView evaluationId="e1" />);

    expect(await screen.findByLabelText(/choose a rubric/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/^marks/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/feedback/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^save$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^submit$/i })).toBeInTheDocument();
  });

  it("flags marks entered above the selected rubric's maximum, client-side", async () => {
    getEvaluation.mockResolvedValue(detail({ status: "IN_PROGRESS", rubric_id: "rubric-1", rubric: rubric() }));
    listCandidateRubrics.mockResolvedValue([rubric()]);

    render(<EvaluationDetailView evaluationId="e1" />);
    const marksInput = await screen.findByLabelText(/^marks/i);
    await userEvent.clear(marksInput);
    await userEvent.type(marksInput, "15");

    expect(await screen.findByText(/marks must be between 0 and/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /^save$/i })).toBeDisabled();
  });

  it("saving calls saveEvaluation with the current form values", async () => {
    getEvaluation.mockResolvedValue(detail({ status: "IN_PROGRESS", rubric_id: "rubric-1", rubric: rubric() }));
    listCandidateRubrics.mockResolvedValue([rubric()]);
    saveEvaluation.mockResolvedValue({});

    render(<EvaluationDetailView evaluationId="e1" />);
    const marksInput = await screen.findByLabelText(/^marks/i);
    await userEvent.clear(marksInput);
    await userEvent.type(marksInput, "8");
    await userEvent.type(screen.getByLabelText(/feedback/i), "Well reasoned.");
    await userEvent.click(screen.getByRole("button", { name: /^save$/i }));

    await waitFor(() =>
      expect(saveEvaluation).toHaveBeenCalledWith("e1", {
        rubric_id: "rubric-1",
        awarded_marks: "8",
        feedback: "Well reasoned.",
      }),
    );
  });

  it("submitting calls the status endpoint with SUBMITTED", async () => {
    getEvaluation.mockResolvedValue(detail({ status: "IN_PROGRESS", rubric_id: "rubric-1", rubric: rubric(), awarded_marks: "8.00" }));
    listCandidateRubrics.mockResolvedValue([rubric()]);
    updateEvaluationStatus.mockResolvedValue({});

    render(<EvaluationDetailView evaluationId="e1" />);
    await userEvent.click(await screen.findByRole("button", { name: /^submit$/i }));

    await waitFor(() => expect(updateEvaluationStatus).toHaveBeenCalledWith("e1", "SUBMITTED"));
  });

  it("finalizing requires confirmation before calling the status endpoint", async () => {
    getEvaluation.mockResolvedValue(
      detail({ status: "SUBMITTED", rubric_id: "rubric-1", rubric: rubric(), awarded_marks: "8.00" }),
    );
    listCandidateRubrics.mockResolvedValue([rubric()]);
    updateEvaluationStatus.mockResolvedValue({});

    render(<EvaluationDetailView evaluationId="e1" />);
    await screen.findByRole("button", { name: /^finalize$/i });

    expect(screen.getByText(/finalize evaluation\?/i)).toBeInTheDocument();
    expect(updateEvaluationStatus).not.toHaveBeenCalled();

    await userEvent.click(screen.getByRole("button", { name: /yes, finalize/i }));

    await waitFor(() => expect(updateEvaluationStatus).toHaveBeenCalledWith("e1", "FINALIZED"));
  });

  it("shows a fully read-only view once FINALIZED, with no editable inputs or actions", async () => {
    getEvaluation.mockResolvedValue(
      detail({
        status: "FINALIZED",
        rubric_id: "rubric-1",
        rubric: rubric(),
        awarded_marks: "8.00",
        feedback: "Well reasoned.",
        finalized_at: "2026-01-02T00:00:00Z",
      }),
    );

    render(<EvaluationDetailView evaluationId="e1" />);

    expect((await screen.findAllByText(/finalized/i)).length).toBeGreaterThanOrEqual(1);
    expect(screen.getByText("Well reasoned.")).toBeInTheDocument();
    expect(screen.queryByLabelText(/choose a rubric/i)).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^save$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^submit$/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^finalize$/i })).not.toBeInTheDocument();
    // listCandidateRubrics is never called once FINALIZED -- nothing left to pick.
    expect(listCandidateRubrics).not.toHaveBeenCalled();
  });

  it("shows a clean not-found state, not a crash, for a revoked/nonexistent evaluation", async () => {
    getEvaluation.mockRejectedValue(new ApiError(404, "Evaluation not found."));

    render(<EvaluationDetailView evaluationId="e1" />);

    expect(await screen.findByText(/could not be found/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /back to workspace/i })).toHaveAttribute(
      "href",
      "/faculty/evaluation-workspace",
    );
  });
});
