import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { getIncomingCollaborations, acceptCollaboration, rejectCollaboration } = vi.hoisted(() => ({
  getIncomingCollaborations: vi.fn(),
  acceptCollaboration: vi.fn(),
  rejectCollaboration: vi.fn(),
}));

vi.mock("@/lib/industry/collaborations", () => ({
  getIncomingCollaborations,
  acceptCollaboration,
  rejectCollaboration,
}));

import { FacultyApplicationsView } from "@/components/faculty/faculty-applications-view";
import { ApiError } from "@/lib/api";

function collaboration(overrides = {}) {
  return {
    id: "c1",
    industry_id: "industry-1",
    recipient_id: "faculty-1",
    recipient_type: "FACULTY",
    title: "Guest lecture on ML",
    description: "desc",
    status: "SENT",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    industry_name: "Acme Corp",
    recipient_name: "Dr. Rao",
    ...overrides,
  };
}

describe("FacultyApplicationsView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders incoming collaboration requests with accept/reject for SENT status", async () => {
    getIncomingCollaborations.mockResolvedValue({ collaborations: [collaboration()] });
    render(<FacultyApplicationsView />);

    expect(await screen.findByText("Guest lecture on ML")).toBeInTheDocument();
    expect(screen.getByText(/Acme Corp/)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /accept/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();
  });

  it("does not show accept/reject for a non-SENT application", async () => {
    getIncomingCollaborations.mockResolvedValue({
      collaborations: [collaboration({ status: "ACCEPTED" })],
    });
    render(<FacultyApplicationsView />);

    await screen.findByText("Guest lecture on ML");
    expect(screen.queryByRole("button", { name: /accept/i })).not.toBeInTheDocument();
    expect(screen.getByText("Accepted")).toBeInTheDocument();
  });

  it("accepting updates the row in place", async () => {
    getIncomingCollaborations.mockResolvedValue({ collaborations: [collaboration()] });
    acceptCollaboration.mockResolvedValue(collaboration({ status: "ACCEPTED" }));

    render(<FacultyApplicationsView />);
    await screen.findByText("Guest lecture on ML");

    await userEvent.click(screen.getByRole("button", { name: /accept/i }));

    await waitFor(() => expect(acceptCollaboration).toHaveBeenCalledWith("c1"));
    expect(await screen.findByText("Accepted")).toBeInTheDocument();
  });

  it("shows an honest empty state when there are none", async () => {
    getIncomingCollaborations.mockResolvedValue({ collaborations: [] });
    render(<FacultyApplicationsView />);
    expect(await screen.findByText(/no collaboration requests/i)).toBeInTheDocument();
  });

  it("shows a retryable error state on load failure", async () => {
    getIncomingCollaborations.mockRejectedValueOnce(new ApiError(500, "Could not load your applications."));
    getIncomingCollaborations.mockResolvedValueOnce({ collaborations: [collaboration()] });

    render(<FacultyApplicationsView />);
    expect(await screen.findByText("Could not load your applications.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Guest lecture on ML")).toBeInTheDocument();
  });
});
