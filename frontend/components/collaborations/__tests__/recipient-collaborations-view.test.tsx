import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getIncomingCollaborations: vi.fn(),
  acceptCollaboration: vi.fn(),
  rejectCollaboration: vi.fn(),
}));

vi.mock("@/lib/industry/collaborations", () => ({
  getIncomingCollaborations: mocks.getIncomingCollaborations,
  acceptCollaboration: mocks.acceptCollaboration,
  rejectCollaboration: mocks.rejectCollaboration,
}));

import { RecipientCollaborationsView } from "@/components/collaborations/recipient-collaborations-view";
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
    status: "SENT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

describe("RecipientCollaborationsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("does not fetch more than once on mount", () => {
    mocks.getIncomingCollaborations.mockReturnValue(new Promise(() => {}));
    render(<RecipientCollaborationsView heading="Collaborations" />);
    expect(mocks.getIncomingCollaborations).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getIncomingCollaborations.mockReturnValue(new Promise(() => {}));
    render(<RecipientCollaborationsView heading="Collaborations" />);
    expect(screen.getByText(/Loading your collaborations/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getIncomingCollaborations.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<RecipientCollaborationsView heading="Collaborations" />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no incoming proposals", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({ collaborations: [] });
    render(<RecipientCollaborationsView heading="Collaborations" />);
    expect(await screen.findByText("No collaboration proposals yet")).toBeInTheDocument();
  });

  it("lists incoming proposals with title, description, and status", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({ collaborations: [collaboration()] });
    render(<RecipientCollaborationsView heading="Collaborations" />);

    expect(await screen.findByText("Joint Research Proposal")).toBeInTheDocument();
    expect(screen.getByText("A proposed research collaboration.")).toBeInTheDocument();
    expect(screen.getByText("Sent")).toBeInTheDocument();
  });

  it("shows which Industry partner a proposal is from when the server resolved it", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({
      collaborations: [collaboration({ industry_name: "TechNova Solutions (DEMO)" })],
    });
    render(<RecipientCollaborationsView heading="Collaborations" />);

    expect(await screen.findByText("From TechNova Solutions (DEMO)")).toBeInTheDocument();
  });

  it("omits the From line when the server did not resolve the Industry name", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({
      collaborations: [collaboration({ industry_name: null })],
    });
    render(<RecipientCollaborationsView heading="Collaborations" />);

    await screen.findByText("Joint Research Proposal");
    expect(screen.queryByText(/^From /)).not.toBeInTheDocument();
  });

  it("shows accept/reject actions only for a SENT proposal", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({
      collaborations: [collaboration({ status: "ACTIVE" })],
    });
    render(<RecipientCollaborationsView heading="Collaborations" />);
    await screen.findByText("Joint Research Proposal");

    expect(screen.queryByRole("button", { name: "Accept" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Reject" })).not.toBeInTheDocument();
    expect(screen.getByText(/Status: Active/i)).toBeInTheDocument();
  });

  it("accepts a proposal through the confirmation dialog", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({ collaborations: [collaboration()] });
    mocks.acceptCollaboration.mockResolvedValueOnce(collaboration({ status: "ACCEPTED" }));

    render(<RecipientCollaborationsView heading="Collaborations" />);
    await screen.findByText("Joint Research Proposal");

    await userEvent.click(screen.getByRole("button", { name: "Accept" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Accept" }));

    await waitFor(() => expect(mocks.acceptCollaboration).toHaveBeenCalledWith("collab-1"));
    expect(await screen.findByText("Proposal accepted.")).toBeInTheDocument();
  });

  it("rejects a proposal through the destructive confirmation dialog", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({ collaborations: [collaboration()] });
    mocks.rejectCollaboration.mockResolvedValueOnce(collaboration({ status: "REJECTED" }));

    render(<RecipientCollaborationsView heading="Collaborations" />);
    await screen.findByText("Joint Research Proposal");

    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Reject" }));

    await waitFor(() => expect(mocks.rejectCollaboration).toHaveBeenCalledWith("collab-1"));
    expect(await screen.findByText("Proposal rejected.")).toBeInTheDocument();
  });

  it("does not call accept until the confirmation dialog is confirmed", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({ collaborations: [collaboration()] });
    render(<RecipientCollaborationsView heading="Collaborations" />);
    await screen.findByText("Joint Research Proposal");

    await userEvent.click(screen.getByRole("button", { name: "Accept" }));
    await screen.findByRole("dialog");

    expect(mocks.acceptCollaboration).not.toHaveBeenCalled();
  });

  it("surfaces an accept error from the API", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({ collaborations: [collaboration()] });
    mocks.acceptCollaboration.mockRejectedValueOnce(new ApiError(409, "Only a sent proposal can be accepted."));

    render(<RecipientCollaborationsView heading="Collaborations" />);
    await screen.findByText("Joint Research Proposal");
    await userEvent.click(screen.getByRole("button", { name: "Accept" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Accept" }));

    expect(await screen.findByText("Only a sent proposal can be accepted.")).toBeInTheDocument();
  });

  it("renders the given heading", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({ collaborations: [] });
    render(<RecipientCollaborationsView heading="Collaborations" />);
    expect(await screen.findByRole("heading", { name: "Collaborations" })).toBeInTheDocument();
  });
});
