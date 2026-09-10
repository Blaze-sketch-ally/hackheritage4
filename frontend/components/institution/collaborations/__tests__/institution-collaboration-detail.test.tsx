import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getCollaboration: vi.fn(),
  acceptCollaboration: vi.fn(),
  rejectCollaboration: vi.fn(),
  createIndustryPartnerRelationship: vi.fn(),
  searchIndustryPartnerCompanies: vi.fn(),
}));

vi.mock("@/lib/industry/collaborations", () => ({
  getCollaboration: mocks.getCollaboration,
  acceptCollaboration: mocks.acceptCollaboration,
  rejectCollaboration: mocks.rejectCollaboration,
}));

vi.mock("@/lib/institution/industry-partners", () => ({
  createIndustryPartnerRelationship: mocks.createIndustryPartnerRelationship,
  updateIndustryPartnerRelationship: vi.fn(),
  searchIndustryPartnerCompanies: mocks.searchIndustryPartnerCompanies,
}));

import { InstitutionCollaborationDetail } from "@/components/institution/collaborations/institution-collaboration-detail";
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

describe("InstitutionCollaborationDetail", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches the collaboration once on mount", () => {
    mocks.getCollaboration.mockReturnValue(new Promise(() => {}));
    render(<InstitutionCollaborationDetail collaborationId="collab-1" />);
    expect(mocks.getCollaboration).toHaveBeenCalledWith("collab-1");
  });

  it("shows a loading state", () => {
    mocks.getCollaboration.mockReturnValue(new Promise(() => {}));
    render(<InstitutionCollaborationDetail collaborationId="collab-1" />);
    expect(screen.getByText(/Loading collaboration/i)).toBeInTheDocument();
  });

  it("shows a not-visible message on 404 (cross-institution isolation)", async () => {
    mocks.getCollaboration.mockRejectedValueOnce(new ApiError(404, "not found"));
    render(<InstitutionCollaborationDetail collaborationId="collab-1" />);
    expect(await screen.findByText(/isn't visible to your institution/i)).toBeInTheDocument();
  });

  it("renders title, company, description, status and dates", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collab());
    render(<InstitutionCollaborationDetail collaborationId="collab-1" />);

    expect(await screen.findByText("AI Research Partnership")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("Joint research initiative.")).toBeInTheDocument();
    expect(screen.getByText("Sent")).toBeInTheDocument();
  });

  it("shows accept/reject only when status is SENT", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collab({ status: "ACTIVE" }));
    render(<InstitutionCollaborationDetail collaborationId="collab-1" />);
    await screen.findByText("AI Research Partnership");
    expect(screen.queryByRole("button", { name: /^accept$/i })).not.toBeInTheDocument();
  });

  it("accepts a SENT proposal after confirmation", async () => {
    const user = userEvent.setup();
    mocks.getCollaboration.mockResolvedValueOnce(collab({ status: "SENT" }));
    mocks.acceptCollaboration.mockResolvedValueOnce(collab({ status: "ACCEPTED" }));
    render(<InstitutionCollaborationDetail collaborationId="collab-1" />);
    await screen.findByText("AI Research Partnership");

    await user.click(screen.getByRole("button", { name: /^accept$/i }));
    await user.click(await screen.findByRole("button", { name: /^accept$/i }));

    expect(mocks.acceptCollaboration).toHaveBeenCalledWith("collab-1");
    expect(await screen.findByText("Proposal accepted.")).toBeInTheDocument();
  });

  it("opens the Add to Industry Partners form pre-filled with this company", async () => {
    mocks.getCollaboration.mockResolvedValueOnce(collab());
    render(<InstitutionCollaborationDetail collaborationId="collab-1" />);
    await screen.findByText("AI Research Partnership");

    fireEvent.click(screen.getByRole("button", { name: /add to industry partners/i }));
    expect(await screen.findByText("Add Industry Partner")).toBeInTheDocument();
    // Company is pinned (read-only), not a searchable picker.
    expect(screen.getAllByText("Acme Corp").length).toBeGreaterThan(0);
  });
});
