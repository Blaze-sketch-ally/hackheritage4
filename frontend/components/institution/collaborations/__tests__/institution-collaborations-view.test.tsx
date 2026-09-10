import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
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

let searchParamsValue = new URLSearchParams();
vi.mock("next/navigation", () => ({
  useSearchParams: () => searchParamsValue,
}));

import { InstitutionCollaborationsView } from "@/components/institution/collaborations/institution-collaborations-view";
import { ApiError } from "@/lib/api";
import type { IndustryCollaboration } from "@/types/industry-collaboration";

function collab(overrides: Partial<IndustryCollaboration> = {}): IndustryCollaboration {
  return {
    id: "collab-1",
    industry_id: "co-1",
    recipient_id: "inst-1",
    recipient_type: "INSTITUTION",
    title: "AI Research Partnership",
    description: "Joint research initiative.",
    status: "SENT",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    industry_name: "Acme Corp",
    recipient_name: "Test Institute",
    ...overrides,
  };
}

describe("InstitutionCollaborationsView", () => {
  afterEach(() => {
    vi.resetAllMocks();
    searchParamsValue = new URLSearchParams();
  });

  it("fetches incoming collaborations once on mount", () => {
    mocks.getIncomingCollaborations.mockReturnValue(new Promise(() => {}));
    render(<InstitutionCollaborationsView />);
    expect(mocks.getIncomingCollaborations).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getIncomingCollaborations.mockReturnValue(new Promise(() => {}));
    render(<InstitutionCollaborationsView />);
    expect(screen.getByText(/Loading your collaborations/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getIncomingCollaborations.mockRejectedValueOnce(new ApiError(500, "boom"));
    render(<InstitutionCollaborationsView />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows an empty state when there are no collaborations", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({ collaborations: [] });
    render(<InstitutionCollaborationsView />);
    expect(await screen.findByText("No collaboration proposals yet")).toBeInTheDocument();
  });

  it("groups collaborations into Pending/Active/Completed sections by real status", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({
      collaborations: [
        collab({ id: "c1", status: "SENT", title: "Pending One" }),
        collab({ id: "c2", status: "ACTIVE", title: "Active One" }),
        collab({ id: "c3", status: "COMPLETED", title: "Completed One" }),
      ],
    });
    render(<InstitutionCollaborationsView />);

    expect(await screen.findByText(/Pending Requests/)).toBeInTheDocument();
    expect(screen.getByText(/Active Collaborations/)).toBeInTheDocument();
    expect(screen.getByText(/Completed Collaborations/)).toBeInTheDocument();
    expect(screen.getByText("Pending One")).toBeInTheDocument();
    expect(screen.getByText("Active One")).toBeInTheDocument();
    expect(screen.getByText("Completed One")).toBeInTheDocument();
  });

  it("shows accept/reject actions only for SENT proposals", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({
      collaborations: [
        collab({ id: "c1", status: "SENT", title: "Pending One" }),
        collab({ id: "c2", status: "ACTIVE", title: "Active One" }),
      ],
    });
    render(<InstitutionCollaborationsView />);
    await screen.findByText("Pending One");

    expect(screen.getAllByRole("button", { name: /^accept$/i })).toHaveLength(1);
    expect(screen.getAllByRole("button", { name: /^reject$/i })).toHaveLength(1);
  });

  it("filters by search term across title and company", async () => {
    const user = userEvent.setup();
    mocks.getIncomingCollaborations.mockResolvedValueOnce({
      collaborations: [
        collab({ id: "c1", status: "SENT", title: "Pending One", industry_name: "Acme Corp" }),
        collab({ id: "c2", status: "ACTIVE", title: "Active One", industry_name: "Globex Inc" }),
      ],
    });
    render(<InstitutionCollaborationsView />);
    await screen.findByText("Pending One");

    await user.type(screen.getByLabelText(/search collaborations/i), "globex");
    expect(screen.queryByText("Pending One")).not.toBeInTheDocument();
    expect(screen.getByText("Active One")).toBeInTheDocument();
  });

  it("initializes the search box from a ?company= query param (Company Detail integration)", async () => {
    searchParamsValue = new URLSearchParams({ company: "Acme" });
    mocks.getIncomingCollaborations.mockResolvedValueOnce({
      collaborations: [
        collab({ id: "c1", status: "SENT", title: "Pending One", industry_name: "Acme Corp" }),
        collab({ id: "c2", status: "ACTIVE", title: "Active One", industry_name: "Globex Inc" }),
      ],
    });
    render(<InstitutionCollaborationsView />);
    expect(await screen.findByText("Pending One")).toBeInTheDocument();
    expect(screen.queryByText("Active One")).not.toBeInTheDocument();
  });

  it("links each collaboration to its detail route", async () => {
    mocks.getIncomingCollaborations.mockResolvedValueOnce({ collaborations: [collab()] });
    render(<InstitutionCollaborationsView />);
    const link = await screen.findByText("AI Research Partnership");
    expect(link.closest("a")).toHaveAttribute("href", "/institution/collaborations/collab-1");
  });
});
