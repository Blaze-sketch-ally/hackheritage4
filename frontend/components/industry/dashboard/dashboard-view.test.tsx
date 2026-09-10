import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getIndustryProfile: vi.fn(),
  getApplicationsSummary: vi.fn(),
  getInternships: vi.fn(),
  getJobs: vi.fn(),
  getProjects: vi.fn(),
  getTrainings: vi.fn(),
  getWorkshops: vi.fn(),
  getMentorshipOpportunities: vi.fn(),
  getCollaborations: vi.fn(),
}));

vi.mock("@/lib/industry/profile", () => ({ getIndustryProfile: mocks.getIndustryProfile }));
vi.mock("@/lib/industry/applications", () => ({ getApplicationsSummary: mocks.getApplicationsSummary }));
vi.mock("@/lib/industry/internships", () => ({ getInternships: mocks.getInternships }));
vi.mock("@/lib/industry/jobs", () => ({ getJobs: mocks.getJobs }));
vi.mock("@/lib/industry/projects", () => ({ getProjects: mocks.getProjects }));
vi.mock("@/lib/industry/training", () => ({ getTrainings: mocks.getTrainings }));
vi.mock("@/lib/industry/workshops", () => ({ getWorkshops: mocks.getWorkshops }));
vi.mock("@/lib/industry/mentorship-opportunities", () => ({
  getMentorshipOpportunities: mocks.getMentorshipOpportunities,
}));
vi.mock("@/lib/industry/collaborations", () => ({ getCollaborations: mocks.getCollaborations }));

import { DashboardView } from "@/components/industry/dashboard/dashboard-view";
import { ApiError } from "@/lib/api";
import type { IndustryProfile } from "@/types/industry";
import type { ApplicationSummary } from "@/types/application";

function profile(overrides: Partial<IndustryProfile> = {}): IndustryProfile {
  return {
    id: "industry-1",
    company_name: "Acme Robotics",
    industry_sector: "Manufacturing",
    company_size: "51-200",
    website_url: "https://acme.test",
    company_description: "We build robots.",
    headquarters_location: "Pune, India",
    founded_year: 2015,
    contact_phone: "+91 20 1234 5678",
    linkedin_url: "https://linkedin.com/company/acme",
    logo_url: "https://acme.test/logo.png",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

function summary(): ApplicationSummary {
  return {
    counts: { APPLIED: 3, UNDER_REVIEW: 1, SHORTLISTED: 0, INTERVIEW_SCHEDULED: 0, SELECTED: 0, REJECTED: 0, WITHDRAWN: 0 },
    total: 4,
  };
}

/** Scopes a query to one module summary card, identified by its title,
 * so assertions on plain digit text (e.g. "1") never collide with the
 * same digit appearing elsewhere on the page (the recruitment funnel
 * also renders bare counts). */
function cardFor(title: string): HTMLElement {
  const el = screen.getByText(title).closest('[data-slot="card"]');
  if (!el) throw new Error(`No card found for title "${title}"`);
  return el as HTMLElement;
}

/** The big total number is always the card's own first <p> -- reading it
 * directly avoids ambiguity with a per-status count that happens to be
 * the same digit (e.g. a card with total=1 and one "Published: 1"). */
function totalIn(card: HTMLElement): string | null {
  return card.querySelector("p")?.textContent ?? null;
}

function mockAllModulesResolved() {
  mocks.getInternships.mockResolvedValue({ internships: [{ id: "i1", status: "DRAFT" }, { id: "i2", status: "PUBLISHED" }] });
  mocks.getJobs.mockResolvedValue({ jobs: [{ id: "j1", status: "PUBLISHED" }] });
  mocks.getProjects.mockResolvedValue({ projects: [] });
  mocks.getTrainings.mockResolvedValue({ trainings: [{ id: "t1", status: "DRAFT" }] });
  mocks.getWorkshops.mockResolvedValue({ workshops: [] });
  mocks.getMentorshipOpportunities.mockResolvedValue({ mentorship_opportunities: [] });
  mocks.getCollaborations.mockResolvedValue({
    collaborations: [{ id: "c1", status: "SENT" }, { id: "c2", status: "ACCEPTED" }],
  });
}

describe("DashboardView", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders a loading state before any data resolves", () => {
    mocks.getIndustryProfile.mockReturnValue(new Promise(() => {}));
    mocks.getApplicationsSummary.mockReturnValue(new Promise(() => {}));
    mocks.getInternships.mockReturnValue(new Promise(() => {}));
    mocks.getJobs.mockReturnValue(new Promise(() => {}));
    mocks.getProjects.mockReturnValue(new Promise(() => {}));
    mocks.getTrainings.mockReturnValue(new Promise(() => {}));
    mocks.getWorkshops.mockReturnValue(new Promise(() => {}));
    mocks.getMentorshipOpportunities.mockReturnValue(new Promise(() => {}));
    mocks.getCollaborations.mockReturnValue(new Promise(() => {}));

    render(<DashboardView />);

    expect(screen.getAllByText("Loading…").length).toBeGreaterThan(0);
    expect(screen.getByText(/Loading your recruitment summary/i)).toBeInTheDocument();
  });

  it("renders successfully with all module data", async () => {
    mocks.getIndustryProfile.mockResolvedValueOnce(profile());
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
    mockAllModulesResolved();

    render(<DashboardView />);

    expect(await screen.findByRole("heading", { name: "Welcome, Acme Robotics" })).toBeInTheDocument();
  });

  it("renders the profile completion section with a working Manage Company Profile link", async () => {
    mocks.getIndustryProfile.mockResolvedValueOnce(profile());
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
    mockAllModulesResolved();

    render(<DashboardView />);

    await screen.findByText("Company Profile");
    expect(screen.getByText("Profile completion")).toBeInTheDocument();
    expect(screen.getByText("100%")).toBeInTheDocument();
    // Base UI <Button render={<Link/>} nativeButton={false}> -> an <a href>
    // exposed with role="button" (same pattern as the rest of the app).
    expect(screen.getByRole("button", { name: /manage company profile/i })).toHaveAttribute(
      "href",
      "/industry/profile",
    );
  });

  it("renders the recruitment pipeline snapshot", async () => {
    mocks.getIndustryProfile.mockResolvedValueOnce(profile());
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
    mockAllModulesResolved();

    render(<DashboardView />);

    expect(await screen.findByText("Recruitment pipeline")).toBeInTheDocument();
    expect(screen.getByText("4 applications")).toBeInTheDocument();
  });

  it("renders all seven module summary cards with correct counts", async () => {
    mocks.getIndustryProfile.mockResolvedValueOnce(profile());
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
    mockAllModulesResolved();

    render(<DashboardView />);

    expect(await screen.findByText("Internships")).toBeInTheDocument();
    expect(screen.getByText("Jobs")).toBeInTheDocument();
    expect(screen.getByText("Projects")).toBeInTheDocument();
    expect(screen.getByText("Training")).toBeInTheDocument();
    expect(screen.getByText("Workshops")).toBeInTheDocument();
    expect(screen.getByText("Mentorship")).toBeInTheDocument();
    expect(screen.getByText("Collaborations")).toBeInTheDocument();

    await waitFor(() => expect(totalIn(cardFor("Internships"))).toBe("2"));
    expect(totalIn(cardFor("Jobs"))).toBe("1");
    expect(totalIn(cardFor("Training"))).toBe("1");
    expect(totalIn(cardFor("Collaborations"))).toBe("2");
  });

  it("handles empty module data (zero-count modules render 'None yet.')", async () => {
    mocks.getIndustryProfile.mockResolvedValueOnce(profile());
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
    mockAllModulesResolved(); // projects, workshops, mentorship all empty arrays

    render(<DashboardView />);

    await screen.findByText("Internships");
    const noneYet = await screen.findAllByText("None yet.");
    expect(noneYet.length).toBe(3); // Projects, Workshops, Mentorship
  });

  it("handles an individual module request failure without crashing the rest of the dashboard", async () => {
    mocks.getIndustryProfile.mockResolvedValueOnce(profile());
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
    mocks.getInternships.mockRejectedValueOnce(new ApiError(500, "Could not load internships."));
    mocks.getJobs.mockResolvedValueOnce({ jobs: [] });
    mocks.getProjects.mockResolvedValueOnce({ projects: [] });
    mocks.getTrainings.mockResolvedValueOnce({ trainings: [] });
    mocks.getWorkshops.mockResolvedValueOnce({ workshops: [] });
    mocks.getMentorshipOpportunities.mockResolvedValueOnce({ mentorship_opportunities: [] });
    mocks.getCollaborations.mockResolvedValueOnce({ collaborations: [] });

    render(<DashboardView />);

    // The failing module shows its own error...
    expect(await screen.findByText("Could not load internships.")).toBeInTheDocument();
    // ...while the rest of the dashboard is still fully usable.
    expect(screen.getByText("Jobs")).toBeInTheDocument();
    expect(screen.getByText("Company Profile")).toBeInTheDocument();
    expect(screen.getByText("Recruitment pipeline")).toBeInTheDocument();
    expect(screen.getAllByText("None yet.").length).toBeGreaterThan(0);
  });

  it("handles profile loading failure appropriately without blocking the rest of the page", async () => {
    mocks.getIndustryProfile.mockRejectedValueOnce(new ApiError(500, "Could not load your company profile."));
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
    mockAllModulesResolved();

    render(<DashboardView />);

    expect(await screen.findByText("Could not load your company profile.")).toBeInTheDocument();
    // Falls back to a generic heading when the profile (and company name) failed to load.
    expect(screen.getByRole("heading", { name: "Dashboard" })).toBeInTheDocument();
    expect(await screen.findByText("Recruitment pipeline")).toBeInTheDocument();
  });

  it("renders correct list-page navigation links for every module", async () => {
    mocks.getIndustryProfile.mockResolvedValueOnce(profile());
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
    mockAllModulesResolved();

    render(<DashboardView />);
    await screen.findByText("Internships");

    const expectations: Array<[string, string]> = [
      ["/industry/internships", "Internships"],
      ["/industry/jobs", "Jobs"],
      ["/industry/projects", "Projects"],
      ["/industry/training", "Training"],
      ["/industry/workshops", "Workshops"],
      ["/industry/mentorship", "Mentorship"],
      ["/industry/collaborations", "Collaborations"],
    ];
    // <Button render={<Link/>} nativeButton={false}> -> <a href role="button">
    const viewAllLinks = screen.getAllByRole("button", { name: "View all" });
    const hrefs = viewAllLinks.map((el) => el.getAttribute("href"));
    for (const [href] of expectations) {
      expect(hrefs).toContain(href);
    }
  });

  it("renders create links correctly for every module and quick action", async () => {
    mocks.getIndustryProfile.mockResolvedValueOnce(profile());
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
    mockAllModulesResolved();

    render(<DashboardView />);
    await screen.findByText("Internships");

    // <Button render={<Link/>} nativeButton={false}> -> <a href role="button">
    expect(screen.getByRole("button", { name: "Post Internship" })).toHaveAttribute(
      "href",
      "/industry/internships/create",
    );
    expect(screen.getByRole("button", { name: "Post Job" })).toHaveAttribute("href", "/industry/jobs/create");
    expect(screen.getByRole("button", { name: "Create Project" })).toHaveAttribute(
      "href",
      "/industry/projects/create",
    );
    expect(screen.getByRole("button", { name: "Create Training" })).toHaveAttribute(
      "href",
      "/industry/training/create",
    );
    expect(screen.getByRole("button", { name: "Create Workshop" })).toHaveAttribute(
      "href",
      "/industry/workshops/create",
    );
    expect(screen.getByRole("button", { name: "Create Mentorship" })).toHaveAttribute(
      "href",
      "/industry/mentorship/create",
    );
    expect(screen.getByRole("button", { name: "Propose Collaboration" })).toHaveAttribute(
      "href",
      "/industry/collaborations/create",
    );
    expect(screen.getByRole("button", { name: "View Applicants" })).toHaveAttribute("href", "/industry/applicants");
  });

  it("gives its Link CTAs nativeButton={false} so Base UI emits no native-button error (QA finding F1)", async () => {
    // Every dashboard CTA is a Base UI <Button> rendered as a <Link> (an
    // <a>), which requires nativeButton={false}. Without it Base UI logs
    // ~20 "...expected a native <button>..." errors per render and puts a
    // stray type="button" on each anchor instead of role="button".
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    try {
      mocks.getIndustryProfile.mockResolvedValueOnce(profile());
      mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
      mockAllModulesResolved();

      render(<DashboardView />);
      await screen.findByText("Internships");
      const manageProfile = await screen.findByRole("button", { name: /manage company profile/i });

      // Deterministic DOM contract of nativeButton={false} on a non-button:
      const ctas = [
        manageProfile,
        ...screen.getAllByRole("button", { name: "View all" }),
        screen.getByRole("button", { name: "Post Internship" }),
        screen.getByRole("button", { name: "Propose Collaboration" }),
      ];
      for (const cta of ctas) {
        expect(cta.tagName).toBe("A");
        expect(cta).not.toHaveAttribute("type");
      }

      const nativeButtonWarnings = errorSpy.mock.calls.filter((args) =>
        args.some((a) => typeof a === "string" && a.includes("expected a native <button>")),
      );
      expect(nativeButtonWarnings).toEqual([]);
    } finally {
      errorSpy.mockRestore();
    }
  });

  it("uses a responsive, non-desktop-only grid for the module summary cards", async () => {
    mocks.getIndustryProfile.mockResolvedValueOnce(profile());
    mocks.getApplicationsSummary.mockResolvedValueOnce(summary());
    mockAllModulesResolved();

    render(<DashboardView />);
    const heading = await screen.findByText("Your opportunities & collaborations");
    const grid = heading.nextElementSibling;
    expect(grid?.className).toMatch(/grid/);
    expect(grid?.className).toMatch(/sm:grid-cols-2/);
    expect(grid?.className).toMatch(/lg:grid-cols-3/);
  });
});
