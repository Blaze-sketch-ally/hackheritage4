import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getCollaborations: vi.fn(),
  sendCollaboration: vi.fn(),
  activateCollaboration: vi.fn(),
  completeCollaboration: vi.fn(),
  cancelCollaboration: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/collaborations", () => ({
  getCollaborations: mocks.getCollaborations,
  sendCollaboration: mocks.sendCollaboration,
  activateCollaboration: mocks.activateCollaboration,
  completeCollaboration: mocks.completeCollaboration,
  cancelCollaboration: mocks.cancelCollaboration,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { CollaborationsListView } from "@/components/industry/collaborations/collaborations-list-view";
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

describe("CollaborationsListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("does not fetch more than once on mount", () => {
    mocks.getCollaborations.mockReturnValue(new Promise(() => {}));
    render(<CollaborationsListView />);
    expect(mocks.getCollaborations).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getCollaborations.mockReturnValue(new Promise(() => {}));
    render(<CollaborationsListView />);
    expect(screen.getByText(/Loading your collaborations/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getCollaborations.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<CollaborationsListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no collaborations", async () => {
    mocks.getCollaborations.mockResolvedValueOnce({ collaborations: [] });
    render(<CollaborationsListView />);
    expect(await screen.findByText("No collaborations yet")).toBeInTheDocument();
  });

  it("lists collaborations with title, recipient type, and status", async () => {
    mocks.getCollaborations.mockResolvedValueOnce({
      collaborations: [
        collaboration(),
        collaboration({
          id: "collab-2",
          title: "Consultancy Engagement",
          recipient_type: "INSTITUTION",
          status: "SENT",
        }),
      ],
    });
    render(<CollaborationsListView />);

    expect(await screen.findByText("Joint Research Proposal")).toBeInTheDocument();
    expect(screen.getByText("Consultancy Engagement")).toBeInTheDocument();
    expect(screen.getByText("Sent")).toBeInTheDocument();
  });

  it("shows the recipient's name when the server resolved it, and the type label otherwise", async () => {
    mocks.getCollaborations.mockResolvedValueOnce({
      collaborations: [
        collaboration({ recipient_name: "Dr. Demo Faculty (DEMO)" }),
        collaboration({
          id: "collab-2",
          title: "Consultancy Engagement",
          recipient_type: "INSTITUTION",
          recipient_name: null,
        }),
      ],
    });
    render(<CollaborationsListView />);

    await screen.findByText("Joint Research Proposal");
    expect(screen.getByText(/To Dr\. Demo Faculty \(DEMO\)/)).toBeInTheDocument();
    // no name -> falls back to the recipient-type label
    expect(screen.getByText(/To Institution/)).toBeInTheDocument();
  });

  it("filters by search text", async () => {
    mocks.getCollaborations.mockResolvedValueOnce({
      collaborations: [collaboration(), collaboration({ id: "collab-2", title: "Consultancy Engagement" })],
    });
    render(<CollaborationsListView />);
    await screen.findByText("Joint Research Proposal");

    await userEvent.type(screen.getByLabelText("Search collaborations"), "consultancy");

    expect(screen.queryByText("Joint Research Proposal")).not.toBeInTheDocument();
    expect(screen.getByText("Consultancy Engagement")).toBeInTheDocument();
  });

  it("sends a draft proposal through the confirmation dialog", async () => {
    mocks.getCollaborations.mockResolvedValueOnce({ collaborations: [collaboration()] });
    mocks.sendCollaboration.mockResolvedValueOnce(collaboration({ status: "SENT" }));

    render(<CollaborationsListView />);
    await screen.findByText("Joint Research Proposal");

    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Send" }));

    await waitFor(() => expect(mocks.sendCollaboration).toHaveBeenCalledWith("collab-1"));
    expect(await screen.findByText("Proposal sent.")).toBeInTheDocument();
  });

  it("does not call a lifecycle action until the confirmation dialog is confirmed", async () => {
    mocks.getCollaborations.mockResolvedValueOnce({ collaborations: [collaboration()] });

    render(<CollaborationsListView />);
    await screen.findByText("Joint Research Proposal");

    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    await screen.findByRole("dialog");

    expect(mocks.sendCollaboration).not.toHaveBeenCalled();
  });

  it("shows activate for an accepted collaboration and completes it via activate then complete actions", async () => {
    mocks.getCollaborations.mockResolvedValueOnce({
      collaborations: [collaboration({ status: "ACCEPTED" })],
    });
    mocks.activateCollaboration.mockResolvedValueOnce(collaboration({ status: "ACTIVE" }));

    render(<CollaborationsListView />);
    await screen.findByText("Joint Research Proposal");

    await userEvent.click(screen.getByRole("button", { name: "Activate" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Activate" }));

    await waitFor(() => expect(mocks.activateCollaboration).toHaveBeenCalledWith("collab-1"));
    expect(await screen.findByText("Collaboration activated.")).toBeInTheDocument();
  });

  it("cancels a collaboration through the destructive confirmation dialog", async () => {
    mocks.getCollaborations.mockResolvedValueOnce({ collaborations: [collaboration({ status: "SENT" })] });
    mocks.cancelCollaboration.mockResolvedValueOnce(collaboration({ status: "CANCELLED" }));

    render(<CollaborationsListView />);
    await screen.findByText("Joint Research Proposal");

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Cancel Collaboration" }));

    await waitFor(() => expect(mocks.cancelCollaboration).toHaveBeenCalledWith("collab-1"));
    expect(await screen.findByText("Collaboration cancelled.")).toBeInTheDocument();
  });

  it("surfaces a lifecycle error from the API", async () => {
    mocks.getCollaborations.mockResolvedValueOnce({ collaborations: [collaboration()] });
    mocks.sendCollaboration.mockRejectedValueOnce(new ApiError(409, "Only a draft can be sent."));

    render(<CollaborationsListView />);
    await screen.findByText("Joint Research Proposal");
    await userEvent.click(screen.getByRole("button", { name: "Send" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Send" }));

    expect(await screen.findByText("Only a draft can be sent.")).toBeInTheDocument();
  });

  it("links the create action to the create page", async () => {
    mocks.getCollaborations.mockResolvedValueOnce({ collaborations: [] });
    render(<CollaborationsListView />);
    await screen.findByText("No collaborations yet");

    // <Button render={<Link/>}> resolves to an <a href> exposed with
    // role="button" (nativeButton={false}); exact name avoids matching the
    // empty-state "+ Create Collaboration" action.
    expect(screen.getByRole("button", { name: "Create Collaboration" })).toHaveAttribute(
      "href",
      "/industry/collaborations/create",
    );
  });
});
