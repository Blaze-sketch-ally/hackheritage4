import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ getPlacementOverview: vi.fn() }));

vi.mock("@/lib/institution/placements", () => ({ getPlacementOverview: mocks.getPlacementOverview }));

import { PlacementDrivesLink } from "@/components/institution/dashboard/placement-drives-link";
import type { PlacementOverviewResponse } from "@/types/institution-placement";

function overview(overrides: Partial<PlacementOverviewResponse> = {}): PlacementOverviewResponse {
  return {
    active_drives: 0,
    completed_drives: 0,
    participating_students: 0,
    placed_students: 0,
    total_selected_offers: 0,
    placement_rate: null,
    department_breakdown: [],
    company_breakdown: [],
    ...overrides,
  };
}

describe("PlacementDrivesLink", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders nothing while loading", () => {
    mocks.getPlacementOverview.mockReturnValue(new Promise(() => {}));
    const { container } = render(<PlacementDrivesLink />);
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing when there are zero drives -- never a fabricated 0-drives card", async () => {
    mocks.getPlacementOverview.mockResolvedValueOnce(overview());
    const { container } = render(<PlacementDrivesLink />);
    await vi.waitFor(() => expect(mocks.getPlacementOverview).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("renders nothing on a fetch error -- this is a supplementary link, not a page-critical metric", async () => {
    mocks.getPlacementOverview.mockRejectedValueOnce(new Error("boom"));
    const { container } = render(<PlacementDrivesLink />);
    await vi.waitFor(() => expect(mocks.getPlacementOverview).toHaveBeenCalled());
    expect(container).toBeEmptyDOMElement();
  });

  it("links to the placements page and shows real active/placed counts", async () => {
    mocks.getPlacementOverview.mockResolvedValueOnce(overview({ active_drives: 2, placed_students: 5 }));
    render(<PlacementDrivesLink />);
    expect(await screen.findByText("Placement Drives")).toBeInTheDocument();
    expect(screen.getByText("2 active · 5 students placed")).toBeInTheDocument();
    expect(screen.getByRole("link")).toHaveAttribute("href", "/institution/placements");
  });
});
