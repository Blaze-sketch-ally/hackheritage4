import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const { getApplicantDetail } = vi.hoisted(() => ({ getApplicantDetail: vi.fn() }));
const { getApplicationPortfolio } = vi.hoisted(() => ({ getApplicationPortfolio: vi.fn() }));

vi.mock("@/lib/industry/opportunities", () => ({ getApplicantDetail }));
vi.mock("@/lib/industry/portfolio", () => ({ getApplicationPortfolio }));

import { ApplicantDetailView } from "@/components/opportunities/applicant-detail-view";
import { ApiError } from "@/lib/api";

function applicant(overrides = {}) {
  return {
    id: "app1",
    student_id: "s1",
    student_name: "Asha Verma",
    status: "APPLIED",
    cover_note: "Excited to apply!",
    overall_match_score: "82.50",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    skills: [
      {
        skill_id: "sk1",
        skill_name: "Python",
        required_level: "70",
        student_score: "90",
        gap: "0",
        weight: "1.0",
        status: "STRONG",
      },
    ],
    ...overrides,
  };
}

function portfolio(overrides = {}) {
  return {
    student_id: "s1",
    projects: [
      {
        id: "p1",
        student_id: "s1",
        title: "Campus Event Finder",
        description: "A React + FastAPI app.",
        technologies: ["React"],
        project_url: null,
        github_url: null,
        created_at: "2026-01-01T00:00:00Z",
        updated_at: "2026-01-01T00:00:00Z",
      },
    ],
    certifications: [],
    ...overrides,
  };
}

describe("ApplicantDetailView", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows a loading state before data arrives", () => {
    getApplicantDetail.mockReturnValue(new Promise(() => {}));
    getApplicationPortfolio.mockReturnValue(new Promise(() => {}));
    render(<ApplicantDetailView opportunityId="o1" applicationId="app1" />);
    expect(screen.getByLabelText("Loading applicant")).toBeInTheDocument();
  });

  it("renders candidate overview, skill alignment, and portfolio once loaded", async () => {
    getApplicantDetail.mockResolvedValue(applicant());
    getApplicationPortfolio.mockResolvedValue(portfolio());
    render(<ApplicantDetailView opportunityId="o1" applicationId="app1" />);

    expect(await screen.findByText("Asha Verma")).toBeInTheDocument();
    expect(screen.getByText("83% match")).toBeInTheDocument();
    expect(screen.getByText("Excited to apply!")).toBeInTheDocument();
    expect(screen.getByText("Skill Alignment")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
    expect(screen.getByText("Campus Event Finder")).toBeInTheDocument();
  });

  it("never renders raw assessment internals alongside the applicant", async () => {
    getApplicantDetail.mockResolvedValue(applicant());
    getApplicationPortfolio.mockResolvedValue(portfolio());
    const { container } = render(<ApplicantDetailView opportunityId="o1" applicationId="app1" />);
    await screen.findByText("Asha Verma");
    expect(container.textContent).not.toMatch(/answer_key|selected_option_ids|correct_option_ids/i);
  });

  it("shows an empty-portfolio state when the candidate has no portfolio content", async () => {
    getApplicantDetail.mockResolvedValue(applicant());
    getApplicationPortfolio.mockResolvedValue(portfolio({ projects: [], certifications: [] }));
    render(<ApplicantDetailView opportunityId="o1" applicationId="app1" />);
    expect(await screen.findByText("This candidate hasn't added any portfolio content yet.")).toBeInTheDocument();
  });

  it("shows a portfolio-unavailable state without blocking the rest of the page when the portfolio fetch fails", async () => {
    getApplicantDetail.mockResolvedValue(applicant());
    getApplicationPortfolio.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));
    render(<ApplicantDetailView opportunityId="o1" applicationId="app1" />);

    expect(await screen.findByText("Asha Verma")).toBeInTheDocument();
    expect(screen.getByText("Portfolio is temporarily unavailable.")).toBeInTheDocument();
  });

  it("shows an unauthorized/not-found state when the applicant fetch 404s", async () => {
    getApplicantDetail.mockRejectedValue(new ApiError(404, "Applicant not found."));
    getApplicationPortfolio.mockResolvedValue(portfolio());
    render(<ApplicantDetailView opportunityId="o1" applicationId="app1" />);
    expect(await screen.findByText("This applicant is not available.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("shows an error state with retry on a generic failure", async () => {
    getApplicantDetail.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));
    getApplicationPortfolio.mockResolvedValue(portfolio());
    render(<ApplicantDetailView opportunityId="o1" applicationId="app1" />);
    expect(await screen.findByText("Backend unavailable right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});
