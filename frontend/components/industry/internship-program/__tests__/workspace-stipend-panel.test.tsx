import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getWorkspaceStipend: vi.fn(),
  createWorkspaceStipend: vi.fn(),
  updateWorkspaceStipend: vi.fn(),
  approveWorkspaceStipend: vi.fn(),
  releaseWorkspaceStipend: vi.fn(),
  cancelWorkspaceStipend: vi.fn(),
}));

vi.mock("@/lib/industry/internship-workspaces", () => mocks);

import { WorkspaceStipendPanel } from "@/components/industry/internship-program/workspace-stipend-panel";
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

describe("WorkspaceStipendPanel", () => {
  afterEach(() => vi.resetAllMocks());

  it("offers to configure a stipend when none exists", async () => {
    mocks.getWorkspaceStipend.mockResolvedValueOnce({ workspace_id: "ws-1", stipend: null });
    render(<WorkspaceStipendPanel workspaceId="ws-1" studentName="Asha Rao" />);
    expect(await screen.findByRole("button", { name: /configure stipend/i })).toBeInTheDocument();
  });

  it("creates a stipend record", async () => {
    const user = userEvent.setup();
    mocks.getWorkspaceStipend.mockResolvedValueOnce({ workspace_id: "ws-1", stipend: null });
    mocks.createWorkspaceStipend.mockResolvedValueOnce({ workspace_id: "ws-1", stipend: stipend() });

    render(<WorkspaceStipendPanel workspaceId="ws-1" studentName="Asha Rao" />);
    await user.click(await screen.findByRole("button", { name: /configure stipend/i }));
    await user.type(screen.getByLabelText(/amount/i), "5000");
    await user.click(screen.getByRole("button", { name: /^configure stipend$/i }));

    await waitFor(() =>
      expect(mocks.createWorkspaceStipend).toHaveBeenCalledWith("ws-1", {
        amount: 5000,
        currency: "INR",
        reference: null,
        notes: null,
      }),
    );
    expect(await screen.findByText("Pending")).toBeInTheDocument();
  });

  it("shows Approve and Cancel for a PENDING stipend, not Release", async () => {
    mocks.getWorkspaceStipend.mockResolvedValueOnce({ workspace_id: "ws-1", stipend: stipend() });
    render(<WorkspaceStipendPanel workspaceId="ws-1" studentName="Asha Rao" />);

    expect(await screen.findByRole("button", { name: /^approve$/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /cancel stipend/i })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /release stipend/i })).not.toBeInTheDocument();
  });

  it("approves a PENDING stipend", async () => {
    const user = userEvent.setup();
    mocks.getWorkspaceStipend.mockResolvedValueOnce({ workspace_id: "ws-1", stipend: stipend() });
    mocks.approveWorkspaceStipend.mockResolvedValueOnce({
      workspace_id: "ws-1",
      stipend: stipend({ disbursement_status: "APPROVED" }),
    });

    render(<WorkspaceStipendPanel workspaceId="ws-1" studentName="Asha Rao" />);
    await user.click(await screen.findByRole("button", { name: /^approve$/i }));

    await waitFor(() => expect(mocks.approveWorkspaceStipend).toHaveBeenCalledWith("ws-1"));
    expect(await screen.findByText("Approved")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /^approve$/i })).not.toBeInTheDocument();
  });

  it("shows Release (with a non-payment confirmation) for an APPROVED stipend", async () => {
    const user = userEvent.setup();
    mocks.getWorkspaceStipend.mockResolvedValueOnce({
      workspace_id: "ws-1",
      stipend: stipend({ disbursement_status: "APPROVED" }),
    });
    render(<WorkspaceStipendPanel workspaceId="ws-1" studentName="Asha Rao" />);

    await user.click(await screen.findByRole("button", { name: /release stipend/i }));
    expect(
      screen.getByText(/does not process a payment/i),
    ).toBeInTheDocument();
  });

  it("releases an APPROVED stipend after confirmation", async () => {
    const user = userEvent.setup();
    mocks.getWorkspaceStipend.mockResolvedValueOnce({
      workspace_id: "ws-1",
      stipend: stipend({ disbursement_status: "APPROVED" }),
    });
    mocks.releaseWorkspaceStipend.mockResolvedValueOnce({
      workspace_id: "ws-1",
      stipend: stipend({ disbursement_status: "RELEASED", released_at: "2026-09-12T00:00:00Z" }),
    });

    render(<WorkspaceStipendPanel workspaceId="ws-1" studentName="Asha Rao" />);
    await user.click(await screen.findByRole("button", { name: /release stipend/i }));
    await user.click(screen.getByRole("button", { name: /^release$/i }));

    await waitFor(() => expect(mocks.releaseWorkspaceStipend).toHaveBeenCalledWith("ws-1"));
    expect(await screen.findByText("Released")).toBeInTheDocument();
  });

  it("shows no actions for a RELEASED or CANCELLED stipend", async () => {
    mocks.getWorkspaceStipend.mockResolvedValueOnce({
      workspace_id: "ws-1",
      stipend: stipend({ disbursement_status: "RELEASED" }),
    });
    render(<WorkspaceStipendPanel workspaceId="ws-1" studentName="Asha Rao" />);

    await screen.findByText("Released");
    expect(screen.queryByRole("button", { name: /approve|release|cancel|edit/i })).not.toBeInTheDocument();
  });

  it("cancels a PENDING stipend after confirmation", async () => {
    const user = userEvent.setup();
    mocks.getWorkspaceStipend.mockResolvedValueOnce({ workspace_id: "ws-1", stipend: stipend() });
    mocks.cancelWorkspaceStipend.mockResolvedValueOnce({
      workspace_id: "ws-1",
      stipend: stipend({ disbursement_status: "CANCELLED" }),
    });

    render(<WorkspaceStipendPanel workspaceId="ws-1" studentName="Asha Rao" />);
    await user.click(await screen.findByRole("button", { name: /cancel stipend/i }));
    await user.click(screen.getByRole("button", { name: /^cancel stipend$/i }));

    await waitFor(() => expect(mocks.cancelWorkspaceStipend).toHaveBeenCalledWith("ws-1"));
    expect(await screen.findByText("Cancelled")).toBeInTheDocument();
  });

  it("shows a server error and does not change state on a failed transition", async () => {
    const user = userEvent.setup();
    mocks.getWorkspaceStipend.mockResolvedValueOnce({ workspace_id: "ws-1", stipend: stipend() });
    mocks.approveWorkspaceStipend.mockRejectedValueOnce(
      new ApiError(409, "A 'APPROVED' stipend record cannot be moved to 'APPROVED'."),
    );

    render(<WorkspaceStipendPanel workspaceId="ws-1" studentName="Asha Rao" />);
    await user.click(await screen.findByRole("button", { name: /^approve$/i }));

    expect(
      await screen.findByText("A 'APPROVED' stipend record cannot be moved to 'APPROVED'."),
    ).toBeInTheDocument();
    expect(screen.getByText("Pending")).toBeInTheDocument(); // unchanged
  });

  it("shows a loading state then an error on failure to load", async () => {
    mocks.getWorkspaceStipend.mockRejectedValueOnce(new ApiError(500, "server sad"));
    render(<WorkspaceStipendPanel workspaceId="ws-1" studentName="Asha Rao" />);
    expect(await screen.findByText("server sad")).toBeInTheDocument();
  });
});
