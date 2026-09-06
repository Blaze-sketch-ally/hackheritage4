import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getMyWorkspaceStipend: vi.fn(),
}));

vi.mock("@/lib/student/internship-workspace", () => mocks);

import { WorkspaceStipend } from "@/components/student/internship-workspace/workspace-stipend";
import { ApiError } from "@/lib/api";
import type { Stipend } from "@/types/internship-stipend";

function stipend(over: Partial<Stipend> = {}): Stipend {
  return {
    id: "stip-1",
    workspace_id: "ws-1",
    amount: 5000,
    currency: "INR",
    disbursement_status: "PENDING",
    reference: null,
    notes: null,
    released_at: null,
    created_at: "2026-09-10T00:00:00Z",
    updated_at: "2026-09-10T00:00:00Z",
    ...over,
  };
}

describe("WorkspaceStipend", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows an honest empty state when no stipend is configured", async () => {
    mocks.getMyWorkspaceStipend.mockResolvedValueOnce({ workspace_id: "ws-1", stipend: null });
    render(<WorkspaceStipend workspaceId="ws-1" />);
    expect(await screen.findByText("No stipend information available yet.")).toBeInTheDocument();
  });

  it("shows a PENDING stipend", async () => {
    mocks.getMyWorkspaceStipend.mockResolvedValueOnce({ workspace_id: "ws-1", stipend: stipend() });
    render(<WorkspaceStipend workspaceId="ws-1" />);
    expect(await screen.findByText("Pending")).toBeInTheDocument();
    expect(screen.getByText(/5,000|5000/)).toBeInTheDocument();
  });

  it("shows an APPROVED stipend", async () => {
    mocks.getMyWorkspaceStipend.mockResolvedValueOnce({
      workspace_id: "ws-1",
      stipend: stipend({ disbursement_status: "APPROVED" }),
    });
    render(<WorkspaceStipend workspaceId="ws-1" />);
    expect(await screen.findByText("Approved")).toBeInTheDocument();
  });

  it("shows a RELEASED stipend without claiming a payment was transferred", async () => {
    mocks.getMyWorkspaceStipend.mockResolvedValueOnce({
      workspace_id: "ws-1",
      stipend: stipend({
        disbursement_status: "RELEASED",
        released_at: "2026-09-12T00:00:00Z",
        reference: "PAYROLL-42",
      }),
    });
    const { container } = render(<WorkspaceStipend workspaceId="ws-1" />);

    expect(await screen.findByText("Released")).toBeInTheDocument();
    expect(screen.getByText(/marked this stipend as released/i)).toBeInTheDocument();
    expect(screen.getByText(/PAYROLL-42/)).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/payment successfully|transferred|paid out/i);
  });

  it("shows a CANCELLED stipend", async () => {
    mocks.getMyWorkspaceStipend.mockResolvedValueOnce({
      workspace_id: "ws-1",
      stipend: stipend({ disbursement_status: "CANCELLED" }),
    });
    render(<WorkspaceStipend workspaceId="ws-1" />);
    expect(await screen.findByText("Cancelled")).toBeInTheDocument();
    expect(screen.getByText("This stipend record was cancelled.")).toBeInTheDocument();
  });

  it("shows a loading state then an error on failure", async () => {
    mocks.getMyWorkspaceStipend.mockRejectedValueOnce(new ApiError(500, "server sad"));
    render(<WorkspaceStipend workspaceId="ws-1" />);
    expect(screen.getByLabelText("Loading stipend status")).toBeInTheDocument();
    expect(await screen.findByText("server sad")).toBeInTheDocument();
  });
});
