import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listOpportunities } = vi.hoisted(() => ({
  listOpportunities: vi.fn(),
}));

vi.mock("@/lib/student/opportunities", () => ({ listOpportunities }));

import { OpportunityListView } from "@/components/opportunities/opportunity-list-view";
import { ApiError } from "@/lib/api";

function opportunity(overrides = {}) {
  return {
    id: "o1",
    industry_id: "i1",
    title: "Backend Developer Internship",
    description: "Build APIs.",
    opportunity_type: "INTERNSHIP",
    location: "Remote",
    status: "PUBLISHED",
    published_at: "2026-01-01T00:00:00Z",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("OpportunityListView", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows a loading state before data arrives", () => {
    listOpportunities.mockReturnValue(new Promise(() => {}));
    render(<OpportunityListView detailBasePath="/student/opportunities" />);
    expect(screen.getByLabelText("Loading opportunities")).toBeInTheDocument();
  });

  it("renders opportunities once loaded, linking to the given detail base path", async () => {
    listOpportunities.mockResolvedValue({ opportunities: [opportunity()] });
    render(<OpportunityListView detailBasePath="/student/internships" />);

    expect(await screen.findByText("Backend Developer Internship")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view details/i })).toHaveAttribute(
      "href",
      "/student/internships/o1",
    );
  });

  it("shows an empty state when there are no opportunities", async () => {
    listOpportunities.mockResolvedValue({ opportunities: [] });
    render(<OpportunityListView detailBasePath="/student/opportunities" />);
    expect(await screen.findByText("No opportunities available right now")).toBeInTheDocument();
  });

  it("shows an error state with retry when the API call fails", async () => {
    listOpportunities.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));
    render(<OpportunityListView detailBasePath="/student/opportunities" />);
    expect(await screen.findByText("Backend unavailable right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("retry re-fetches the list", async () => {
    listOpportunities
      .mockRejectedValueOnce(new ApiError(500, "Backend unavailable right now."))
      .mockResolvedValueOnce({ opportunities: [opportunity()] });
    render(<OpportunityListView detailBasePath="/student/opportunities" />);
    await screen.findByText("Backend unavailable right now.");

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(listOpportunities).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Backend Developer Internship")).toBeInTheDocument();
  });

  it("does not show the type toggle when a lockedType is given", async () => {
    listOpportunities.mockResolvedValue({ opportunities: [] });
    render(<OpportunityListView lockedType="JOB" detailBasePath="/student/jobs" />);
    await screen.findByText("No opportunities available right now");
    expect(screen.queryByRole("button", { name: "All" })).not.toBeInTheDocument();
  });

  it("switching the type toggle re-fetches with the selected type", async () => {
    listOpportunities.mockResolvedValue({ opportunities: [] });
    render(<OpportunityListView detailBasePath="/student/opportunities" />);
    await screen.findByText("No opportunities available right now");

    await userEvent.click(screen.getByRole("button", { name: "Jobs" }));

    await waitFor(() => expect(listOpportunities).toHaveBeenLastCalledWith("JOB"));
  });

  it("never renders private industry or scoring internals on the list", async () => {
    listOpportunities.mockResolvedValue({ opportunities: [opportunity()] });
    render(<OpportunityListView detailBasePath="/student/opportunities" />);
    await screen.findByText("Backend Developer Internship");
    expect(screen.queryByText(/industry_id/i)).not.toBeInTheDocument();
  });
});
