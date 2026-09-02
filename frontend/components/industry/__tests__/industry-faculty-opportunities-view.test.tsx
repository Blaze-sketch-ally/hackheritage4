import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const { listOwnFacultyOpportunities, listFacultyOpportunityEois } = vi.hoisted(() => ({
  listOwnFacultyOpportunities: vi.fn(),
  listFacultyOpportunityEois: vi.fn(),
}));

vi.mock("@/lib/industry/faculty-opportunities", () => ({
  listOwnFacultyOpportunities,
  createFacultyOpportunity: vi.fn(),
  updateFacultyOpportunity: vi.fn(),
  publishFacultyOpportunity: vi.fn(),
  closeFacultyOpportunity: vi.fn(),
  listFacultyOpportunityEois,
  reviewFacultyOpportunityEoi: vi.fn(),
  updateEngagementStatus: vi.fn(),
}));

import { IndustryFacultyOpportunitiesView } from "@/components/industry/industry-faculty-opportunities-view";

describe("IndustryFacultyOpportunitiesView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("wires the Industry-specific lib functions into the shared management view", async () => {
    listOwnFacultyOpportunities.mockResolvedValue({ opportunities: [] });
    listFacultyOpportunityEois.mockResolvedValue({ expressions: [] });

    render(<IndustryFacultyOpportunitiesView />);

    await waitFor(() => expect(listOwnFacultyOpportunities).toHaveBeenCalled());
    expect(await screen.findByText(/haven't created any faculty opportunities/i)).toBeInTheDocument();
  });
});
