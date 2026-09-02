import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listOpportunities: vi.fn(),
}));

vi.mock("@/lib/student/opportunities", () => ({
  listOpportunities: mocks.listOpportunities,
}));

import { OpportunityListView } from "@/components/student/opportunities/opportunity-list-view";
import { ApiError } from "@/lib/api";
import type { StudentOpportunitySummary } from "@/types/student-opportunity";

function opportunity(overrides: Partial<StudentOpportunitySummary> = {}): StudentOpportunitySummary {
  return {
    id: "internship_11111111-1111-1111-1111-111111111111",
    source_type: "INTERNSHIP",
    title: "Backend Intern",
    description: "Build APIs with us.",
    location: "Pune",
    work_mode: "HYBRID",
    status: "PUBLISHED",
    industry: { id: "industry-1", company_name: "Acme", industry_sector: null, logo_url: null },
    application_deadline: "2026-12-01",
    created_at: "2026-09-01T00:00:00Z",
    has_applied: false,
    ...overrides,
  };
}

describe("OpportunityListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.listOpportunities.mockReturnValue(new Promise(() => {}));
    render(<OpportunityListView sourceType="INTERNSHIP" detailBasePath="/student/internships" />);
    expect(screen.getByLabelText("Loading opportunities")).toBeInTheDocument();
  });

  it("renders opportunity cards with title and company", async () => {
    mocks.listOpportunities.mockResolvedValueOnce({
      opportunities: [
        opportunity(),
        opportunity({ id: "internship_2", title: "Data Intern", has_applied: true }),
      ],
    });
    render(<OpportunityListView sourceType="INTERNSHIP" detailBasePath="/student/internships" />);

    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText("Data Intern")).toBeInTheDocument();
    expect(screen.getAllByText("Acme")).toHaveLength(2);
    expect(screen.getByText("Applied")).toBeInTheDocument();
  });

  it("passes the locked source type to the API", async () => {
    mocks.listOpportunities.mockResolvedValueOnce({ opportunities: [] });
    render(<OpportunityListView sourceType="JOB" detailBasePath="/student/jobs" />);
    await screen.findByText(/No jobs available/i);
    expect(mocks.listOpportunities).toHaveBeenCalledWith({ sourceType: "JOB" });
  });

  it("shows the empty state", async () => {
    mocks.listOpportunities.mockResolvedValueOnce({ opportunities: [] });
    render(<OpportunityListView sourceType="INTERNSHIP" detailBasePath="/student/internships" />);
    expect(await screen.findByText(/No internships available right now/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.listOpportunities.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<OpportunityListView sourceType="INTERNSHIP" detailBasePath="/student/internships" />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("filters the rendered list by title search", async () => {
    mocks.listOpportunities.mockResolvedValueOnce({
      opportunities: [opportunity(), opportunity({ id: "internship_2", title: "Data Science Intern" })],
    });
    render(<OpportunityListView sourceType="INTERNSHIP" detailBasePath="/student/internships" />);
    await screen.findByText("Backend Intern");

    await userEvent.type(screen.getByLabelText("Search internships"), "data");

    expect(screen.queryByText("Backend Intern")).not.toBeInTheDocument();
    expect(screen.getByText("Data Science Intern")).toBeInTheDocument();
  });
});
