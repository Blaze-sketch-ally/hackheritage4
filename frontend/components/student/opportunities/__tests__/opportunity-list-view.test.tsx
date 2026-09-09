import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

// Debounced URL writes + async fetches mean some assertions genuinely need
// to wait past the 1s default -- especially when the whole suite runs in
// parallel. Every async assertion in this file uses this budget.
const T = { timeout: 5000 } as const;

const mocks = vi.hoisted(() => ({
  listOpportunities: vi.fn(),
  replace: vi.fn(),
  searchParams: new URLSearchParams(),
  pathname: "/student/internships",
}));

vi.mock("@/lib/student/opportunities", () => ({
  listOpportunities: mocks.listOpportunities,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: mocks.replace }),
  usePathname: () => mocks.pathname,
  useSearchParams: () => mocks.searchParams,
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

/** Simulate the URL the component reads (initial mount, or after a
 * back/forward). Tests call this before render / rerender. */
function setUrl(qs: string) {
  mocks.searchParams = new URLSearchParams(qs);
}

function renderInternships() {
  mocks.pathname = "/student/internships";
  return render(
    <OpportunityListView sourceType="INTERNSHIP" detailBasePath="/student/internships" />,
  );
}

function renderJobs() {
  mocks.pathname = "/student/jobs";
  return render(<OpportunityListView sourceType="JOB" detailBasePath="/student/jobs" />);
}

describe("OpportunityListView", () => {
  beforeEach(() => {
    setUrl("");
    mocks.listOpportunities.mockResolvedValue({ opportunities: [] });
  });
  afterEach(() => {
    vi.clearAllMocks();
  });

  // ---- existing behaviour (kept) ----

  it("shows a loading state", () => {
    mocks.listOpportunities.mockReturnValue(new Promise(() => {}));
    renderInternships();
    expect(screen.getByLabelText("Loading opportunities")).toBeInTheDocument();
  });

  it("renders opportunity cards with title and company (no client-side filtering)", async () => {
    mocks.listOpportunities.mockResolvedValueOnce({
      opportunities: [
        opportunity(),
        opportunity({ id: "internship_2", title: "Data Intern", has_applied: true }),
      ],
    });
    renderInternships();

    expect(await screen.findByText("Backend Intern", undefined, T)).toBeInTheDocument();
    expect(screen.getByText("Data Intern")).toBeInTheDocument();
    expect(screen.getAllByText("Acme")).toHaveLength(2);
    expect(screen.getByText("Applied")).toBeInTheDocument();
  });

  it("passes the locked source type to the API", async () => {
    renderJobs();
    await waitFor(
      () =>
        expect(mocks.listOpportunities).toHaveBeenCalledWith(
          expect.objectContaining({ sourceType: "JOB" }),
        ),
      T,
    );
  });

  it("shows the no-data empty state when nothing is published and no filters are active", async () => {
    renderInternships();
    expect(
      await screen.findByText(/No internships available right now/i, undefined, T),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reset filters/i })).not.toBeInTheDocument();
  });

  it("shows an error state with retry, and retry refetches", async () => {
    mocks.listOpportunities
      .mockRejectedValueOnce(new ApiError(500, "Server is down."))
      .mockResolvedValueOnce({ opportunities: [opportunity()] });
    renderInternships();

    expect(await screen.findByText("Server is down.", undefined, T)).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Backend Intern", undefined, T)).toBeInTheDocument();
  });

  it("navigates to the detail route via the card link", async () => {
    mocks.listOpportunities.mockResolvedValueOnce({ opportunities: [opportunity()] });
    const { container } = renderInternships();
    await screen.findByText("Backend Intern", undefined, T);
    expect(
      container.querySelector(
        'a[href="/student/internships/internship_11111111-1111-1111-1111-111111111111"]',
      ),
    ).not.toBeNull();
  });

  // ---- filter controls present ----

  it("renders the search box, work-mode, sort and stipend controls for internships", () => {
    renderInternships();
    expect(screen.getByLabelText("Search internships")).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /filter by work mode/i })).toBeInTheDocument();
    expect(screen.getByRole("combobox", { name: /sort opportunities/i })).toBeInTheDocument();
    expect(
      screen.getByRole("combobox", { name: /filter by minimum stipend/i }),
    ).toBeInTheDocument();
    expect(screen.queryByRole("combobox", { name: /minimum salary/i })).not.toBeInTheDocument();
  });

  it("renders the salary control (not stipend) for jobs", () => {
    renderJobs();
    expect(
      screen.getByRole("combobox", { name: /filter by minimum salary/i }),
    ).toBeInTheDocument();
    expect(
      screen.queryByRole("combobox", { name: /minimum stipend/i }),
    ).not.toBeInTheDocument();
  });

  // ---- initial URL params seed the fetch ----

  it("sends work_mode, sort and min_stipend from the initial URL", async () => {
    setUrl("search=react&work_mode=REMOTE&min_stipend=20000&order_by=deadline");
    renderInternships();
    await waitFor(
      () =>
        expect(mocks.listOpportunities).toHaveBeenCalledWith({
          sourceType: "INTERNSHIP",
          search: "react",
          workMode: "REMOTE",
          minStipend: 20000,
          minSalary: undefined,
          sort: "deadline",
        }),
      T,
    );
  });

  it("sends min_salary from the initial URL for jobs", async () => {
    setUrl("work_mode=HYBRID&min_salary=1000000");
    renderJobs();
    await waitFor(
      () =>
        expect(mocks.listOpportunities).toHaveBeenCalledWith({
          sourceType: "JOB",
          search: undefined,
          workMode: "HYBRID",
          minStipend: undefined,
          minSalary: 1000000,
          sort: "newest",
        }),
      T,
    );
  });

  it("sanitizes an invalid URL and still fires a clean request", async () => {
    setUrl("work_mode=banana&order_by=cheapest&min_stipend=abc");
    renderInternships();
    await waitFor(
      () =>
        expect(mocks.listOpportunities).toHaveBeenCalledWith({
          sourceType: "INTERNSHIP",
          search: undefined,
          workMode: undefined,
          minStipend: undefined,
          minSalary: undefined,
          sort: "newest",
        }),
      T,
    );
    expect(mocks.replace).not.toHaveBeenCalled();
  });

  // ---- search -> debounced URL update ----

  it("debounces the search box into a router.replace with the query string", async () => {
    renderInternships();
    await screen.findByText(/No internships/i, undefined, T);

    await userEvent.type(screen.getByLabelText("Search internships"), "react");

    await waitFor(
      () =>
        expect(mocks.replace).toHaveBeenCalledWith("/student/internships?search=react", {
          scroll: false,
        }),
      T,
    );
    // one settled write, not one per keystroke
    expect(mocks.replace).toHaveBeenCalledTimes(1);
  });

  // ---- reset ----

  it("Reset clears the query string via router.replace and is hidden by default", async () => {
    setUrl("search=react&work_mode=REMOTE");
    renderInternships();
    await screen.findByText(/No internships/i, undefined, T);

    await userEvent.click(screen.getByRole("button", { name: /^reset$/i }));
    expect(mocks.replace).toHaveBeenCalledWith("/student/internships", { scroll: false });
  });

  it("does not render the Reset button when no filter is active", () => {
    setUrl("");
    renderInternships();
    expect(screen.queryByRole("button", { name: /^reset$/i })).not.toBeInTheDocument();
  });

  // ---- filtered-empty vs no-data ----

  it("shows the filtered-empty state (with Reset) when filters match nothing", async () => {
    setUrl("work_mode=ONSITE&min_stipend=30000");
    mocks.listOpportunities.mockResolvedValueOnce({ opportunities: [] });
    renderInternships();

    expect(
      await screen.findByText(/No internships match your filters/i, undefined, T),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reset filters/i })).toBeInTheDocument();
    expect(screen.queryByText(/available right now/i)).not.toBeInTheDocument();
  });

  // ---- back / forward ----

  it("refetches with the restored filters when the URL changes (back/forward)", async () => {
    setUrl("");
    const view = renderInternships();
    await waitFor(
      () =>
        expect(mocks.listOpportunities).toHaveBeenLastCalledWith(
          expect.objectContaining({ sourceType: "INTERNSHIP", workMode: undefined }),
        ),
      T,
    );

    setUrl("work_mode=REMOTE&order_by=deadline");
    view.rerender(
      <OpportunityListView sourceType="INTERNSHIP" detailBasePath="/student/internships" />,
    );

    await waitFor(
      () =>
        expect(mocks.listOpportunities).toHaveBeenLastCalledWith(
          expect.objectContaining({ workMode: "REMOTE", sort: "deadline" }),
        ),
      T,
    );
  });

  it("does not loop: a stable URL fetches once and never rewrites the URL", async () => {
    setUrl("work_mode=REMOTE");
    renderInternships();
    await waitFor(() => expect(mocks.listOpportunities).toHaveBeenCalled(), T);
    // let any stray render/effect settle
    await new Promise((r) => setTimeout(r, 200));
    expect(mocks.listOpportunities).toHaveBeenCalledTimes(1);
    expect(mocks.replace).not.toHaveBeenCalled();
  });
});
