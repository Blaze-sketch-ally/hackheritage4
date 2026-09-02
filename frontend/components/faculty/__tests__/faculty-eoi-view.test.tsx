import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listMyExpressions, withdrawExpression } = vi.hoisted(() => ({
  listMyExpressions: vi.fn(),
  withdrawExpression: vi.fn(),
}));

vi.mock("@/lib/faculty/opportunities", () => ({
  listMyExpressions,
  withdrawExpression,
}));

import { FacultyEoiView } from "@/components/faculty/faculty-eoi-view";
import { ApiError } from "@/lib/api";

function expression(overrides = {}) {
  return {
    id: "eoi-1",
    source: "INDUSTRY",
    opportunity_id: "o1",
    opportunity_title: "Data Science Research Collaboration",
    faculty_id: "faculty-1",
    status: "SUBMITTED",
    message: "Interested.",
    reviewed_by: null,
    reviewer_note: null,
    created_at: "2026-02-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
    engagement: null,
    ...overrides,
  };
}

function engagement(overrides = {}) {
  return {
    id: "eng-1",
    source_kind: "INDUSTRY_EOI",
    industry_eoi_id: "eoi-1",
    institution_eoi_id: null,
    faculty_id: "faculty-1",
    organization_id: "industry-1",
    status: "PLANNED",
    start_date: null,
    end_date: null,
    notes: null,
    created_at: "2026-02-02T00:00:00Z",
    updated_at: "2026-02-02T00:00:00Z",
    ...overrides,
  };
}

describe("FacultyEoiView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders the caller's own expressions of interest with a withdraw action for pending states", async () => {
    listMyExpressions.mockResolvedValue({ expressions: [expression()] });
    render(<FacultyEoiView />);

    expect(await screen.findByText("Data Science Research Collaboration")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /withdraw/i })).toBeInTheDocument();
  });

  it("does not show withdraw for a terminal state", async () => {
    listMyExpressions.mockResolvedValue({ expressions: [expression({ status: "ACCEPTED" })] });
    render(<FacultyEoiView />);

    await screen.findByText("Data Science Research Collaboration");
    expect(screen.queryByRole("button", { name: /withdraw/i })).not.toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();
  });

  it("withdrawing updates the row in place", async () => {
    listMyExpressions.mockResolvedValue({ expressions: [expression()] });
    withdrawExpression.mockResolvedValue(expression({ status: "WITHDRAWN" }));

    render(<FacultyEoiView />);
    await screen.findByText("Data Science Research Collaboration");

    await userEvent.click(screen.getByRole("button", { name: /withdraw/i }));

    await waitFor(() => expect(withdrawExpression).toHaveBeenCalledWith("INDUSTRY", "eoi-1"));
    expect(await screen.findByText("Withdrawn")).toBeInTheDocument();
  });

  it("shows an honest empty state when there are none", async () => {
    listMyExpressions.mockResolvedValue({ expressions: [] });
    render(<FacultyEoiView />);
    expect(await screen.findByText(/haven't expressed interest/i)).toBeInTheDocument();
  });

  it("shows the resulting engagement's status for an accepted EOI (Phase F4.1)", async () => {
    listMyExpressions.mockResolvedValue({
      expressions: [expression({ status: "ACCEPTED", engagement: engagement() })],
    });
    render(<FacultyEoiView />);

    await screen.findByText("Data Science Research Collaboration");
    expect(screen.getByText(/engagement:\s*planned/i)).toBeInTheDocument();
  });

  it("shows nothing extra for an EOI with no engagement yet", async () => {
    listMyExpressions.mockResolvedValue({ expressions: [expression()] });
    render(<FacultyEoiView />);

    await screen.findByText("Data Science Research Collaboration");
    expect(screen.queryByText(/engagement:/i)).not.toBeInTheDocument();
  });

  it("shows a retryable error state on load failure", async () => {
    listMyExpressions.mockRejectedValueOnce(new ApiError(500, "Could not load your expressions of interest."));
    listMyExpressions.mockResolvedValueOnce({ expressions: [expression()] });

    render(<FacultyEoiView />);
    expect(await screen.findByText("Could not load your expressions of interest.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Data Science Research Collaboration")).toBeInTheDocument();
  });
});
