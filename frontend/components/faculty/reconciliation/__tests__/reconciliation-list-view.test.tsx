import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ listReconciliationCases: vi.fn() }));

vi.mock("@/lib/faculty/reconciliation", () => ({
  listReconciliationCases: mocks.listReconciliationCases,
}));

import { ReconciliationListView } from "@/components/faculty/reconciliation/reconciliation-list-view";
import { ApiError } from "@/lib/api";
import type { ReconciliationCaseSummary } from "@/types/reconciliation";

function caseSummary(overrides: Partial<ReconciliationCaseSummary> = {}): ReconciliationCaseSummary {
  return {
    attempt_id: "at-1",
    assessment_id: "a-1",
    assessment_title: "Python Basics",
    student_label: "Student abcd1234",
    question_id: "q-1",
    question_text: "Explain closures.",
    points: "10.00",
    ...overrides,
  };
}

describe("ReconciliationListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.listReconciliationCases.mockReturnValue(new Promise(() => {}));
    render(<ReconciliationListView />);
    expect(screen.getByLabelText("Loading reconciliation cases")).toBeInTheDocument();
  });

  it("renders real cases with assessment, student label, and question", async () => {
    mocks.listReconciliationCases.mockResolvedValueOnce({ cases: [caseSummary()] });
    render(<ReconciliationListView />);

    expect(await screen.findByText("Python Basics")).toBeInTheDocument();
    expect(screen.getByText("Student abcd1234")).toBeInTheDocument();
    expect(screen.getByText("Explain closures.")).toBeInTheDocument();
  });

  it("shows an honest empty state (no fabricated cases)", async () => {
    mocks.listReconciliationCases.mockResolvedValueOnce({ cases: [] });
    render(<ReconciliationListView />);
    expect(await screen.findByText("No reconciliation cases.")).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.listReconciliationCases.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<ReconciliationListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("links each case to its attempt-scoped detail page", async () => {
    mocks.listReconciliationCases.mockResolvedValueOnce({ cases: [caseSummary({ attempt_id: "at-42" })] });
    const { container } = render(<ReconciliationListView />);
    await screen.findByText("Python Basics");
    expect(container.querySelector('a[href="/faculty/reconciliation/at-42"]')).not.toBeNull();
  });

  it("never renders a resolve or decide action", async () => {
    mocks.listReconciliationCases.mockResolvedValueOnce({ cases: [caseSummary()] });
    render(<ReconciliationListView />);
    await screen.findByText("Python Basics");
    expect(screen.queryByRole("button", { name: /resolve|decide|finalize/i })).not.toBeInTheDocument();
  });
});
