import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const { listOwnFacultyOpportunities, listFacultyOpportunityEois } = vi.hoisted(() => ({
  listOwnFacultyOpportunities: vi.fn(),
  listFacultyOpportunityEois: vi.fn(),
}));

vi.mock("@/lib/institution/faculty-opportunities", () => ({
  listOwnFacultyOpportunities,
  createFacultyOpportunity: vi.fn(),
  updateFacultyOpportunity: vi.fn(),
  publishFacultyOpportunity: vi.fn(),
  closeFacultyOpportunity: vi.fn(),
  listFacultyOpportunityEois,
  reviewFacultyOpportunityEoi: vi.fn(),
  updateEngagementStatus: vi.fn(),
}));

import { InstitutionFacultyOpportunitiesView } from "@/components/institution/institution-faculty-opportunities-view";

describe("InstitutionFacultyOpportunitiesView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("wires the Institution-specific lib functions into the shared management view", async () => {
    listOwnFacultyOpportunities.mockResolvedValue({ opportunities: [] });
    listFacultyOpportunityEois.mockResolvedValue({ expressions: [] });

    render(<InstitutionFacultyOpportunitiesView />);

    await waitFor(() => expect(listOwnFacultyOpportunities).toHaveBeenCalled());
    expect(await screen.findByText(/haven't created any faculty opportunities/i)).toBeInTheDocument();
  });
});
