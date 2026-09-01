import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getCollaboration: vi.fn(),
  updateCollaboration: vi.fn(),
  sendCollaboration: vi.fn(),
  activateCollaboration: vi.fn(),
  completeCollaboration: vi.fn(),
  cancelCollaboration: vi.fn(),
  resolveRecipient: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/collaborations", () => ({
  getCollaboration: mocks.getCollaboration,
  updateCollaboration: mocks.updateCollaboration,
  sendCollaboration: mocks.sendCollaboration,
  activateCollaboration: mocks.activateCollaboration,
  completeCollaboration: mocks.completeCollaboration,
  cancelCollaboration: mocks.cancelCollaboration,
  resolveRecipient: mocks.resolveRecipient,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { CollaborationDetailView } from "@/components/industry/collaborations/collaboration-detail-view";
import { ApiError } from "@/lib/api";
import type { IndustryCollaboration } from "@/types/industry-collaboration";

function collaboration(overrides: Partial<IndustryCollaboration> = {}): IndustryCollaboration {
  return {
    id: "collab-1",
    industry_id: "industry-1",
    recipient_id: "faculty-1",
    recipient_type: "FACULTY",
    title: "Joint Research Proposal",
    description: "A proposed research collaboration.",
    status: "DRAFT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

describe("CollaborationDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getCollaboration.mockReturnValue(new Promise(() => {}));
    render(<CollaborationDetailView collaborationId="collab-1" />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows a not-found message on a 404", async () => {
    mocks.getCollaboration.mockRejectedValueOnce(new ApiError(404, "Collaboration not found."));
    render(<CollaborationDetailView collaborationId="collab-x" />);
    expect(await screen.findByText(/doesn't exist or isn't yours/i)).toBeInTheDocument();
  });

  it("renders collaboration detail with status and recipient type", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collaboration());
    render(<CollaborationDetailView collaborationId="collab-1" />);

    expect(
      await screen.findByRole("heading", { name: "Joint Research Proposal" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Faculty")).toBeInTheDocument();
  });

  it("shows the resolved recipient name alongside the type when the server provides it", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(
      collaboration({ recipient_name: "Demo Institution Office (DEMO)", recipient_type: "INSTITUTION" }),
    );
    render(<CollaborationDetailView collaborationId="collab-1" />);

    expect(await screen.findByText("Name")).toBeInTheDocument();
    expect(screen.getByText("Demo Institution Office (DEMO)")).toBeInTheDocument();
    expect(screen.getByText("Institution")).toBeInTheDocument();
  });

  it("omits the recipient Name field when the server did not resolve it", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collaboration({ recipient_name: null }));
    render(<CollaborationDetailView collaborationId="collab-1" />);

    await screen.findByText("Faculty");
    expect(screen.queryByText("Name")).not.toBeInTheDocument();
  });

  it("switches to the edit form and saves changes without touching the recipient", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collaboration());
    mocks.updateCollaboration.mockResolvedValueOnce(collaboration({ title: "Updated Proposal" }));

    render(<CollaborationDetailView collaborationId="collab-1" />);
    await screen.findByRole("heading", { name: "Joint Research Proposal" });

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const title = await screen.findByLabelText("Title");
    await userEvent.clear(title);
    await userEvent.type(title, "Updated Proposal");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(mocks.updateCollaboration).toHaveBeenCalledTimes(1));
    expect(mocks.updateCollaboration.mock.calls[0][0]).toBe("collab-1");
    expect(mocks.updateCollaboration.mock.calls[0][1]).toEqual({
      title: "Updated Proposal",
      description: "A proposed research collaboration.",
    });
    expect(await screen.findByText("Changes saved.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Updated Proposal" })).toBeInTheDocument();
  });

  it("does not show an edit action once sent", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collaboration({ status: "SENT" }));
    render(<CollaborationDetailView collaborationId="collab-1" />);
    await screen.findByRole("heading", { name: "Joint Research Proposal" });
    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
  });

  it("sends via the confirmation dialog", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collaboration());
    mocks.sendCollaboration.mockResolvedValueOnce(collaboration({ status: "SENT" }));

    render(<CollaborationDetailView collaborationId="collab-1" />);
    await screen.findByRole("heading", { name: "Joint Research Proposal" });

    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Send" }));

    await waitFor(() => expect(mocks.sendCollaboration).toHaveBeenCalledWith("collab-1"));
    expect(await screen.findByText("Proposal sent.")).toBeInTheDocument();
    expect(screen.getByText("Sent")).toBeInTheDocument();
  });

  it("activates an accepted collaboration", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collaboration({ status: "ACCEPTED" }));
    mocks.activateCollaboration.mockResolvedValueOnce(collaboration({ status: "ACTIVE" }));

    render(<CollaborationDetailView collaborationId="collab-1" />);
    await screen.findByRole("heading", { name: "Joint Research Proposal" });

    await userEvent.click(screen.getByRole("button", { name: "Activate" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Activate" }));

    await waitFor(() => expect(mocks.activateCollaboration).toHaveBeenCalledWith("collab-1"));
    expect(await screen.findByText("Collaboration activated.")).toBeInTheDocument();
  });

  it("completes an active collaboration", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collaboration({ status: "ACTIVE" }));
    mocks.completeCollaboration.mockResolvedValueOnce(collaboration({ status: "COMPLETED" }));

    render(<CollaborationDetailView collaborationId="collab-1" />);
    await screen.findByRole("heading", { name: "Joint Research Proposal" });

    await userEvent.click(screen.getByRole("button", { name: "Complete" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Complete" }));

    await waitFor(() => expect(mocks.completeCollaboration).toHaveBeenCalledWith("collab-1"));
    expect(await screen.findByText("Collaboration completed.")).toBeInTheDocument();
  });

  it("cancels via the destructive confirmation dialog", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collaboration({ status: "SENT" }));
    mocks.cancelCollaboration.mockResolvedValueOnce(collaboration({ status: "CANCELLED" }));

    render(<CollaborationDetailView collaborationId="collab-1" />);
    await screen.findByRole("heading", { name: "Joint Research Proposal" });

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel Collaboration" }));

    await waitFor(() => expect(mocks.cancelCollaboration).toHaveBeenCalledWith("collab-1"));
    expect(await screen.findByText("Collaboration cancelled.")).toBeInTheDocument();
  });

  it("starts in edit mode when initialEdit is set", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collaboration());
    render(<CollaborationDetailView collaborationId="collab-1" initialEdit />);

    expect(await screen.findByRole("heading", { name: "Edit Collaboration" })).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Joint Research Proposal");
  });
});
