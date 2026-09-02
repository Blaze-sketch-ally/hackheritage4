import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({ getPortfolio: vi.fn() }));
vi.mock("@/lib/student/portfolio", () => ({ getPortfolio: mocks.getPortfolio }));

import { PortfolioView } from "@/components/student/portfolio/portfolio-view";
import { ApiError } from "@/lib/api";
import type { PortfolioResponse } from "@/types/student-portfolio";

const FULL: PortfolioResponse = {
  projects: [
    {
      id: "p1",
      title: "Skill Portal",
      description: "A portfolio app.",
      project_url: "https://example.com",
      repo_url: "https://github.com/me/x",
      start_date: "2026-01-01",
      end_date: null,
      is_ongoing: true,
      skills: [{ skill_id: "s1", skill_name: "Python", category_name: "Programming" }],
      created_at: null,
      updated_at: null,
    },
  ],
  certifications: [
    {
      id: "c1",
      name: "AWS CCP",
      issuing_organization: "AWS",
      issue_date: "2026-02-01",
      expiry_date: null,
      credential_id: null,
      credential_url: "https://verify.example.com/1",
      created_at: null,
      updated_at: null,
    },
  ],
  achievements: [
    {
      id: "a1",
      title: "Hackathon Winner",
      description: null,
      achievement_date: "2026-08-30",
      issuing_organization: "AIC",
      url: null,
      created_at: null,
      updated_at: null,
    },
  ],
  skills: [
    {
      skill_id: "s1",
      skill_name: "Python",
      category_name: "Programming",
      proficiency_level: "Advanced",
      is_verified: true,
    },
  ],
};

const EMPTY: PortfolioResponse = { projects: [], certifications: [], achievements: [], skills: [] };

describe("PortfolioView", () => {
  afterEach(() => vi.resetAllMocks());

  it("aggregates the student's real projects / certifications / achievements / skills", async () => {
    mocks.getPortfolio.mockResolvedValue(FULL);
    render(<PortfolioView displayName="Demo Student" headline="Aspiring backend dev" />);

    expect(await screen.findByText("Skill Portal")).toBeInTheDocument();
    expect(screen.getByText("AWS CCP")).toBeInTheDocument();
    expect(screen.getByText("Hackathon Winner")).toBeInTheDocument();
    expect(screen.getByText("Demo Student")).toBeInTheDocument();
    expect(screen.getByText("Aspiring backend dev")).toBeInTheDocument();
    // section counts come straight from the arrays -- not fabricated
    expect(screen.getByText("Projects").parentElement?.textContent).toContain("(1)");
    expect(screen.getByText("Skills").parentElement?.textContent).toContain("(1)");
    // verified skill shows its real proficiency, not an invented score
    expect(screen.getByText(/Python · Advanced/)).toBeInTheDocument();
    // no fabricated portfolio statistics
    expect(screen.queryByText(/%/)).not.toBeInTheDocument();
  });

  it("shows an honest empty state with add actions when the portfolio has no content", async () => {
    mocks.getPortfolio.mockResolvedValue(EMPTY);
    const { container } = render(<PortfolioView displayName="New Student" headline={null} />);
    expect(await screen.findByText("Your portfolio is empty")).toBeInTheDocument();
    expect(container.querySelector('a[href="/student/projects"]')).not.toBeNull();
    expect(container.querySelector('a[href="/student/certifications"]')).not.toBeNull();
    expect(container.querySelector('a[href="/student/achievements"]')).not.toBeNull();
    expect(container.querySelector('a[href="/student/skills"]')).not.toBeNull();
  });

  it("shows an error state with retry", async () => {
    mocks.getPortfolio.mockRejectedValueOnce(new ApiError(500, "boom")).mockResolvedValueOnce(EMPTY);
    render(<PortfolioView displayName="X" headline={null} />);
    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Your portfolio is empty")).toBeInTheDocument();
  });
});
