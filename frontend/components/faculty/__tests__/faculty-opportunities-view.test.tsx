import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listFacultyOpportunities, expressInterest } = vi.hoisted(() => ({
  listFacultyOpportunities: vi.fn(),
  expressInterest: vi.fn(),
}));

vi.mock("@/lib/faculty/opportunities", () => ({
  listFacultyOpportunities,
  expressInterest,
}));

import { FacultyOpportunitiesView } from "@/components/faculty/faculty-opportunities-view";
import { ApiError } from "@/lib/api";

function opportunity(overrides = {}) {
  return {
    id: "o1",
    source: "INDUSTRY",
    owner_id: "industry-1",
    owner_name: "Acme Corp",
    title: "Data Science Research Collaboration",
    description: "Collaborate on a joint dataset.",
    location: "Remote",
    work_mode: "REMOTE",
    capacity: 2,
    eligibility_criteria: null,
    application_deadline: "2026-06-01",
    start_date: "2026-07-01",
    status: "PUBLISHED",
    created_at: "2026-02-01T00:00:00Z",
    updated_at: "2026-02-01T00:00:00Z",
    ...overrides,
  };
}

describe("FacultyOpportunitiesView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("renders published opportunities with their source and organization", async () => {
    listFacultyOpportunities.mockResolvedValue({ opportunities: [opportunity()] });
    render(<FacultyOpportunitiesView />);

    expect(await screen.findByText("Data Science Research Collaboration")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getAllByText("Industry").length).toBe(2); // filter button + badge
  });

  it("shows an honest empty state when there are none", async () => {
    listFacultyOpportunities.mockResolvedValue({ opportunities: [] });
    render(<FacultyOpportunitiesView />);
    expect(await screen.findByText(/no published opportunities right now/i)).toBeInTheDocument();
  });

  it("shows a retryable error state on load failure", async () => {
    listFacultyOpportunities.mockRejectedValueOnce(new ApiError(500, "Could not load opportunities."));
    listFacultyOpportunities.mockResolvedValueOnce({ opportunities: [opportunity()] });

    render(<FacultyOpportunitiesView />);
    expect(await screen.findByText("Could not load opportunities.")).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Data Science Research Collaboration")).toBeInTheDocument();
  });

  it("re-fetches with the selected source filter", async () => {
    listFacultyOpportunities.mockResolvedValue({ opportunities: [] });
    render(<FacultyOpportunitiesView />);
    await waitFor(() => expect(listFacultyOpportunities).toHaveBeenCalledWith(undefined));

    await userEvent.click(screen.getByRole("button", { name: "Institution" }));

    await waitFor(() => expect(listFacultyOpportunities).toHaveBeenCalledWith("INSTITUTION"));
  });

  it("submits an expression of interest with a message", async () => {
    listFacultyOpportunities.mockResolvedValue({ opportunities: [opportunity()] });
    expressInterest.mockResolvedValue({
      id: "eoi-1",
      source: "INDUSTRY",
      opportunity_id: "o1",
      faculty_id: "faculty-1",
      status: "SUBMITTED",
      message: "Interested!",
      reviewed_by: null,
      reviewer_note: null,
      created_at: null,
      updated_at: null,
    });

    render(<FacultyOpportunitiesView />);
    await screen.findByText("Data Science Research Collaboration");

    await userEvent.click(screen.getByRole("button", { name: /express interest/i }));
    await userEvent.type(screen.getByPlaceholderText(/optional message/i), "Interested!");
    await userEvent.click(screen.getByRole("button", { name: /submit/i }));

    await waitFor(() => expect(expressInterest).toHaveBeenCalledWith("INDUSTRY", "o1", "Interested!"));
    expect(await screen.findByText(/expression of interest has been submitted/i)).toBeInTheDocument();
  });

  it("shows an error inside the dialog without closing it on failure", async () => {
    listFacultyOpportunities.mockResolvedValue({ opportunities: [opportunity()] });
    expressInterest.mockRejectedValue(new ApiError(409, "You have already expressed interest in this opportunity."));

    render(<FacultyOpportunitiesView />);
    await screen.findByText("Data Science Research Collaboration");

    await userEvent.click(screen.getByRole("button", { name: /express interest/i }));
    await userEvent.click(screen.getByRole("button", { name: /submit/i }));

    expect(await screen.findByText("You have already expressed interest in this opportunity.")).toBeInTheDocument();
  });
});
