import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ getReconciliationCase: vi.fn() }));

vi.mock("@/lib/faculty/reconciliation", () => ({
  getReconciliationCase: mocks.getReconciliationCase,
}));

import { ReconciliationDetailView } from "@/components/faculty/reconciliation/reconciliation-detail-view";
import { ApiError } from "@/lib/api";
import type { ReconciliationEvaluatorMark } from "@/types/reconciliation";

function mark(overrides: Partial<ReconciliationEvaluatorMark> = {}): ReconciliationEvaluatorMark {
  return {
    question_id: "q-1",
    question_text: "Explain closures.",
    points: "10.00",
    evaluator_id: "11111111-1111-1111-1111-111111111111",
    awarded_marks: "7.00",
    feedback: "Good but incomplete.",
    rubric_id: "r-1",
    rubric_name: "Closures Rubric",
    finalized_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("ReconciliationDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getReconciliationCase.mockReturnValue(new Promise(() => {}));
    render(<ReconciliationDetailView attemptId="at-1" />);
    expect(screen.getByLabelText("Loading reconciliation case")).toBeInTheDocument();
  });

  it("shows both evaluators' marks side by side, fully preserved and distinct", async () => {
    mocks.getReconciliationCase.mockResolvedValueOnce({
      attempt_id: "at-1",
      marks: [
        mark({ evaluator_id: "11111111-1111-1111-1111-111111111111", awarded_marks: "4.00" }),
        mark({ evaluator_id: "22222222-2222-2222-2222-222222222222", awarded_marks: "9.00" }),
      ],
    });
    render(<ReconciliationDetailView attemptId="at-1" />);

    expect(await screen.findByText("Explain closures.")).toBeInTheDocument();
    expect(screen.getByText("4.00 pts")).toBeInTheDocument();
    expect(screen.getByText("9.00 pts")).toBeInTheDocument();
  });

  it("groups marks by question when an attempt has multiple conflicting questions", async () => {
    mocks.getReconciliationCase.mockResolvedValueOnce({
      attempt_id: "at-1",
      marks: [
        mark({ question_id: "q-1", question_text: "Explain closures." }),
        mark({ question_id: "q-2", question_text: "Explain recursion.", evaluator_id: "33333333-3333-3333-3333-333333333333" }),
      ],
    });
    render(<ReconciliationDetailView attemptId="at-1" />);

    expect(await screen.findByText("Explain closures.")).toBeInTheDocument();
    expect(screen.getByText("Explain recursion.")).toBeInTheDocument();
  });

  it("shows a not-found state for a case that no longer exists or is already resolved", async () => {
    mocks.getReconciliationCase.mockRejectedValueOnce(new ApiError(404, "not found"));
    render(<ReconciliationDetailView attemptId="at-1" />);
    expect(await screen.findByText("This is not a current reconciliation case.")).toBeInTheDocument();
  });

  it("shows an error state with retry for a genuine failure", async () => {
    mocks.getReconciliationCase.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<ReconciliationDetailView attemptId="at-1" />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("never renders a resolve or decide action", async () => {
    mocks.getReconciliationCase.mockResolvedValueOnce({ attempt_id: "at-1", marks: [mark()] });
    render(<ReconciliationDetailView attemptId="at-1" />);
    await screen.findByText("Explain closures.");
    expect(screen.queryByRole("button", { name: /resolve|decide|finalize/i })).not.toBeInTheDocument();
  });
});
