import { createContext, useContext, type ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { useFacultyCapabilitiesContext } = vi.hoisted(() => ({
  useFacultyCapabilitiesContext: vi.fn(),
}));

vi.mock("@/lib/faculty/capabilities", async () => {
  const actual = await vi.importActual<typeof import("@/lib/faculty/capabilities")>("@/lib/faculty/capabilities");
  return { ...actual, useFacultyCapabilitiesContext };
});

/** See the identical mock in question-create-form.test.tsx: the real
 * @base-ui/react Select this project's components/ui/select.tsx wraps
 * reliably hangs for tens of seconds under this project's jsdom test
 * setup (both opening its popup and driving its accessible autofill
 * hidden-input were tried and both hung). A native <select> -- built
 * from the same `items` label map the real component already receives
 * -- is behaviorally equivalent for what these tests check (which value
 * ends up selected), so this file replaces the real component with one
 * for its four filter/sort Select usages. Production code
 * (question-bank-view.tsx) is untouched; this mock exists only here. */
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

const { listMyQuestions, approveQuestion, rejectQuestion } = vi.hoisted(() => ({
  listMyQuestions: vi.fn(),
  approveQuestion: vi.fn(),
  rejectQuestion: vi.fn(),
}));

vi.mock("@/lib/faculty/question-bank", () => ({
  listMyQuestions,
  approveQuestion,
  rejectQuestion,
}));

vi.mock("@/hooks/use-auth", () => ({
  useAuth: () => ({ user: { id: "faculty-me" } }),
}));

import { QuestionBankView } from "@/components/faculty/question-bank-view";
import { ApiError } from "@/lib/api";

function question(overrides = {}) {
  return {
    id: "q1",
    assessment_id: "a1",
    question_text: "What is a closure?",
    question_type: "MCQ",
    scoring_method: "OBJECTIVE",
    difficulty: "Intermediate",
    points: "5.00",
    display_order: 0,
    learning_objective: null,
    estimated_time_minutes: null,
    review_status: "PENDING",
    is_active: true,
    created_by: "faculty-other",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    options: [],
    answer_key: null,
    ...overrides,
  };
}

describe("QuestionBankView", () => {
  beforeEach(() => {
    // Reviewer by default -- this file's own existing tests are about
    // reviewer actions (approve/reject); author-specific "New question"
    // visibility is covered by its own dedicated tests below.
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_reviewer"] });
  });

  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows the New question action only for a caller with assessment_author", async () => {
    useFacultyCapabilitiesContext.mockReturnValue({ status: "ready", capabilities: ["assessment_author"] });
    listMyQuestions.mockResolvedValue([question({ id: "q1", created_by: "faculty-me" })]);

    render(<QuestionBankView />);
    await screen.findByText("What is a closure?");

    expect(screen.getByRole("button", { name: /new question/i })).toHaveAttribute("href", "/faculty/questions/new");
  });

  it("hides the New question action for a reviewer without author capability", async () => {
    listMyQuestions.mockResolvedValue([question({ id: "q1", created_by: "faculty-other" })]);

    render(<QuestionBankView />);
    await screen.findByText("What is a closure?");

    expect(screen.queryByRole("button", { name: /new question/i })).not.toBeInTheDocument();
  });

  it("shows Approve/Reject only for another setter's PENDING question, never for the caller's own", async () => {
    listMyQuestions.mockResolvedValue([
      question({ id: "q1", question_text: "Other setter's question", created_by: "faculty-other", review_status: "PENDING" }),
      question({ id: "q2", question_text: "My own question", created_by: "faculty-me", review_status: "PENDING" }),
    ]);

    render(<QuestionBankView />);

    expect(await screen.findByText("Other setter's question")).toBeInTheDocument();
    expect(screen.getByText("My own question")).toBeInTheDocument();
    const approveButtons = screen.getAllByRole("button", { name: /approve/i });
    // Only one row (the other setter's) gets an Approve button.
    expect(approveButtons).toHaveLength(1);
    expect(screen.getByText("Awaiting another setter")).toBeInTheDocument();
  });

  it("approving a question calls the API and updates the row in place", async () => {
    listMyQuestions.mockResolvedValue([question({ id: "q1", created_by: "faculty-other" })]);
    approveQuestion.mockResolvedValue(question({ id: "q1", created_by: "faculty-other", review_status: "APPROVED" }));

    render(<QuestionBankView />);
    await screen.findByText("What is a closure?");

    await userEvent.click(screen.getByRole("button", { name: /approve/i }));

    await waitFor(() => expect(approveQuestion).toHaveBeenCalledWith("q1"));
    // Scoped to the table -- Phase F6.5's status filter Select also has an
    // "Approved" option, and (only in this test file's native-<select>
    // mock, not in the real popup-based component) every <option> is
    // unconditionally present in the DOM, so a bare screen-wide query
    // would now match both.
    expect(await within(screen.getByRole("table")).findByText("Approved")).toBeInTheDocument();
  });

  it("shows a retryable error state on load failure", async () => {
    listMyQuestions.mockRejectedValueOnce(new ApiError(500, "Could not load questions."));
    listMyQuestions.mockResolvedValueOnce([question()]);

    render(<QuestionBankView />);

    expect(await screen.findByText("Could not load questions.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    expect(await screen.findByText("What is a closure?")).toBeInTheDocument();
    expect(listMyQuestions).toHaveBeenCalledTimes(2);
  });

  it("shows an empty state when there are no questions", async () => {
    listMyQuestions.mockResolvedValue([]);
    render(<QuestionBankView />);
    expect(await screen.findByText(/no questions yet/i)).toBeInTheDocument();
  });

  // ============================================================
  // Phase F6.5 -- client-side search/filter/sort
  // ============================================================

  it("searches by question text without making a new API call", async () => {
    listMyQuestions.mockResolvedValue([
      question({ id: "q1", question_text: "What is a closure?" }),
      question({ id: "q2", question_text: "Explain recursion." }),
    ]);
    render(<QuestionBankView />);
    await screen.findByText("What is a closure?");

    await userEvent.type(screen.getByLabelText("Search questions"), "closure");

    expect(screen.getByText("What is a closure?")).toBeInTheDocument();
    expect(screen.queryByText("Explain recursion.")).not.toBeInTheDocument();
    expect(listMyQuestions).toHaveBeenCalledTimes(1);
  });

  it("filters by question type", async () => {
    listMyQuestions.mockResolvedValue([
      question({ id: "q1", question_text: "MCQ question", question_type: "MCQ" }),
      question({ id: "q2", question_text: "Short answer question", question_type: "SHORT_ANSWER" }),
    ]);
    render(<QuestionBankView />);
    await screen.findByText("MCQ question");

    await changeSelect("Filter by question type", "SHORT_ANSWER");

    await waitFor(() => expect(screen.queryByText("MCQ question")).not.toBeInTheDocument());
    expect(screen.getByText("Short answer question")).toBeInTheDocument();
  });

  it("filters by review status", async () => {
    listMyQuestions.mockResolvedValue([
      question({ id: "q1", question_text: "Pending question", review_status: "PENDING" }),
      question({ id: "q2", question_text: "Approved question", review_status: "APPROVED" }),
    ]);
    render(<QuestionBankView />);
    await screen.findByText("Pending question");

    await changeSelect("Filter by status", "APPROVED");

    await waitFor(() => expect(screen.queryByText("Pending question")).not.toBeInTheDocument());
    expect(screen.getByText("Approved question")).toBeInTheDocument();
  });

  it("filters by difficulty", async () => {
    listMyQuestions.mockResolvedValue([
      question({ id: "q1", question_text: "Easy question", difficulty: "Beginner" }),
      question({ id: "q2", question_text: "Hard question", difficulty: "Expert" }),
    ]);
    render(<QuestionBankView />);
    await screen.findByText("Easy question");

    await changeSelect("Filter by difficulty", "Expert");

    await waitFor(() => expect(screen.queryByText("Easy question")).not.toBeInTheDocument());
    expect(screen.getByText("Hard question")).toBeInTheDocument();
  });

  it("sorts newest/oldest by created_at", async () => {
    listMyQuestions.mockResolvedValue([
      question({ id: "q1", question_text: "Older question", created_at: "2026-01-01T00:00:00Z" }),
      question({ id: "q2", question_text: "Newer question", created_at: "2026-02-01T00:00:00Z" }),
    ]);
    render(<QuestionBankView />);
    await screen.findByText("Older question");

    function rowOrder() {
      return screen.getAllByRole("row").slice(1).map((row) => row.textContent);
    }

    // Default sort is "newest first".
    expect(rowOrder()[0]).toContain("Newer question");

    await changeSelect("Sort questions", "oldest");

    await waitFor(() => expect(rowOrder()[0]).toContain("Older question"));
  });

  it("shows a no-match empty state with a reset action when filters exclude everything", async () => {
    listMyQuestions.mockResolvedValue([question({ id: "q1", question_text: "What is a closure?" })]);
    render(<QuestionBankView />);
    await screen.findByText("What is a closure?");

    await userEvent.type(screen.getByLabelText("Search questions"), "nonexistent topic");

    expect(await screen.findByText(/no questions match your search or filters/i)).toBeInTheDocument();

    // Two "Reset filters" buttons render at once here -- the filter bar's
    // own (visible whenever any filter is active) and the empty state's
    // -- either does the same thing, so click whichever is found first.
    await userEvent.click(screen.getAllByRole("button", { name: /reset filters/i })[0]);

    expect(await screen.findByText("What is a closure?")).toBeInTheDocument();
  });
});
