import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getOpportunity: vi.fn(),
  getOpportunityMatch: vi.fn(),
  listMyApplications: vi.fn(),
  applyToOpportunity: vi.fn(),
}));

vi.mock("@/lib/student/opportunities", () => ({
  getOpportunity: mocks.getOpportunity,
  getOpportunityMatch: mocks.getOpportunityMatch,
  listMyApplications: mocks.listMyApplications,
  applyToOpportunity: mocks.applyToOpportunity,
}));

import { OpportunityDetailView } from "@/components/student/opportunities/opportunity-detail-view";
import { ApiError } from "@/lib/api";
import type {
  OpportunityMatch,
  StudentApplication,
  StudentOpportunityDetail,
} from "@/types/student-opportunity";

const OPP_ID = "internship_11111111-1111-1111-1111-111111111111";

function detail(overrides: Partial<StudentOpportunityDetail> = {}): StudentOpportunityDetail {
  return {
    id: OPP_ID,
    source_type: "INTERNSHIP",
    title: "Backend Intern",
    description: "Build APIs.",
    location: "Pune",
    work_mode: "HYBRID",
    status: "PUBLISHED",
    industry: { id: "industry-1", company_name: "Acme", industry_sector: "SaaS", logo_url: null },
    application_deadline: "2026-12-01",
    created_at: "2026-09-01T00:00:00Z",
    has_applied: false,
    eligibility_criteria: "CS students",
    openings: 2,
    duration_months: 6,
    stipend_amount: 15000,
    stipend_currency: "INR",
    start_date: null,
    employment_type: null,
    salary_min: null,
    salary_max: null,
    salary_currency: null,
    experience_min_years: null,
    skills: [
      {
        skill_id: "s1",
        skill_name: "Python",
        category_name: "Programming",
        required_level: "Intermediate",
        importance: "CORE",
      },
    ],
    ...overrides,
  };
}

function application(overrides: Partial<StudentApplication> = {}): StudentApplication {
  return {
    id: "app-1",
    student_id: "student-1",
    opportunity_type: "INTERNSHIP",
    internship_id: "11111111-1111-1111-1111-111111111111",
    job_id: null,
    status: "APPLIED",
    cover_note: null,
    match_score: null,
    applied_at: "2026-09-02T00:00:00Z",
    created_at: "2026-09-02T00:00:00Z",
    updated_at: "2026-09-02T00:00:00Z",
    opportunity: { id: OPP_ID, source_type: "INTERNSHIP", title: "Backend Intern", industry: null, location: "Pune", work_mode: "HYBRID" },
    ...overrides,
  };
}

const noMatch: OpportunityMatch = {
  opportunity_id: OPP_ID,
  score: 0,
  recommendation: "LOW",
  skill_coverage: "0 / 0",
  required_count: 0,
  matched_count: 0,
  needs_improvement_count: 0,
  missing_count: 0,
  matched_skills: [],
  needs_improvement_skills: [],
  missing_skills: [],
};

describe("OpportunityDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders the opportunity with requirements", async () => {
    mocks.getOpportunity.mockResolvedValueOnce(detail());
    mocks.listMyApplications.mockResolvedValueOnce({ applications: [] });
    mocks.getOpportunityMatch.mockResolvedValueOnce(noMatch);

    render(<OpportunityDetailView opportunityId={OPP_ID} />);

    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText("Requirements")).toBeInTheDocument();
    expect(screen.getByText(/Python · Intermediate/)).toBeInTheDocument();
  });

  it("shows a not-available message on a 404", async () => {
    mocks.getOpportunity.mockRejectedValueOnce(new ApiError(404, "not found"));
    mocks.listMyApplications.mockResolvedValueOnce({ applications: [] });

    render(<OpportunityDetailView opportunityId={OPP_ID} />);
    expect(await screen.findByText("This opportunity is not available.")).toBeInTheDocument();
  });

  it("submits an application with a cover note", async () => {
    mocks.getOpportunity.mockResolvedValueOnce(detail());
    mocks.listMyApplications.mockResolvedValueOnce({ applications: [] });
    mocks.getOpportunityMatch.mockResolvedValueOnce(noMatch);
    mocks.applyToOpportunity.mockResolvedValueOnce(application());

    render(<OpportunityDetailView opportunityId={OPP_ID} />);
    await screen.findByText("Backend Intern");

    await userEvent.type(screen.getByLabelText(/Cover note/i), "I love APIs");
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));

    await waitFor(() =>
      expect(mocks.applyToOpportunity).toHaveBeenCalledWith(OPP_ID, "I love APIs"),
    );
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument(),
    );
    expect(screen.getAllByText("Applied").length).toBeGreaterThan(0);
  });

  it("shows a friendly message when the application is a duplicate (409)", async () => {
    mocks.getOpportunity.mockResolvedValueOnce(detail());
    mocks.listMyApplications.mockResolvedValueOnce({ applications: [] });
    mocks.getOpportunityMatch.mockResolvedValueOnce(noMatch);
    mocks.applyToOpportunity.mockRejectedValueOnce(new ApiError(409, "You have already applied to this opportunity."));

    render(<OpportunityDetailView opportunityId={OPP_ID} />);
    await screen.findByText("Backend Intern");
    await userEvent.click(screen.getByRole("button", { name: "Apply" }));

    expect(await screen.findByText(/already applied/i)).toBeInTheDocument();
  });

  it("shows the current status instead of the apply form when already applied", async () => {
    mocks.getOpportunity.mockResolvedValueOnce(detail({ has_applied: true }));
    mocks.listMyApplications.mockResolvedValueOnce({
      applications: [application({ status: "INTERVIEW_SCHEDULED" })],
    });
    mocks.getOpportunityMatch.mockResolvedValueOnce(noMatch);

    render(<OpportunityDetailView opportunityId={OPP_ID} />);

    expect(await screen.findByText("Interview Scheduled")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Apply" })).not.toBeInTheDocument();
  });

  it("still renders the posting when the match call fails", async () => {
    mocks.getOpportunity.mockResolvedValueOnce(detail());
    mocks.listMyApplications.mockResolvedValueOnce({ applications: [] });
    mocks.getOpportunityMatch.mockRejectedValueOnce(new ApiError(500, "match down"));

    render(<OpportunityDetailView opportunityId={OPP_ID} />);
    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Apply" })).toBeInTheDocument();
  });
});
