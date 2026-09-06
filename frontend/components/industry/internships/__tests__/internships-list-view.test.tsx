import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getInternships: vi.fn(),
  publishInternship: vi.fn(),
  closeInternship: vi.fn(),
  archiveInternship: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/internships", () => ({
  getInternships: mocks.getInternships,
  publishInternship: mocks.publishInternship,
  closeInternship: mocks.closeInternship,
  archiveInternship: mocks.archiveInternship,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { InternshipsListView } from "@/components/industry/internships/internships-list-view";
import { ApiError } from "@/lib/api";
import type { Internship, InternshipStatus } from "@/types/internship";

function internship(overrides: Partial<Internship> = {}): Internship {
  return {
    id: "int-1",
    industry_id: "industry-1",
    title: "Backend Intern",
    description: "APIs.",
    location: "Pune",
    work_mode: "HYBRID",
    duration_months: 6,
    stipend_amount: 15000,
    stipend_currency: "INR",
    openings: 2,
    eligibility_criteria: null,
    application_deadline: "2026-12-01",
    start_date: null,
    status: "DRAFT" as InternshipStatus,
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
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

describe("InternshipsListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getInternships.mockReturnValue(new Promise(() => {}));
    render(<InternshipsListView />);
    expect(screen.getByText(/Loading your internships/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getInternships.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<InternshipsListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no internships", async () => {
    mocks.getInternships.mockResolvedValueOnce({ internships: [] });
    render(<InternshipsListView />);
    expect(await screen.findByText("No internships yet")).toBeInTheDocument();
  });

  it("lists internships with title, status and skill count", async () => {
    mocks.getInternships.mockResolvedValueOnce({
      internships: [internship(), internship({ id: "int-2", title: "Data Intern", status: "PUBLISHED" })],
    });
    render(<InternshipsListView />);

    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText("Data Intern")).toBeInTheDocument();
    expect(screen.getAllByText(/1 required skill/)).toHaveLength(2);
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("filters by search text", async () => {
    mocks.getInternships.mockResolvedValueOnce({
      internships: [internship(), internship({ id: "int-2", title: "Data Science Intern" })],
    });
    render(<InternshipsListView />);
    await screen.findByText("Backend Intern");

    await userEvent.type(screen.getByLabelText("Search internships"), "data");

    expect(screen.queryByText("Backend Intern")).not.toBeInTheDocument();
    expect(screen.getByText("Data Science Intern")).toBeInTheDocument();
  });

  it("publishes an internship through the confirmation dialog", async () => {
    mocks.getInternships.mockResolvedValueOnce({ internships: [internship()] });
    mocks.publishInternship.mockResolvedValueOnce(internship({ status: "PUBLISHED" }));

    render(<InternshipsListView />);
    await screen.findByText("Backend Intern");

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));

    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishInternship).toHaveBeenCalledWith("int-1"));
    expect(await screen.findByText("Internship published.")).toBeInTheDocument();
  });

  it("surfaces a publish error from the API", async () => {
    mocks.getInternships.mockResolvedValueOnce({ internships: [internship()] });
    mocks.publishInternship.mockRejectedValueOnce(
      new ApiError(422, "This internship isn't ready to publish. Add: location."),
    );

    render(<InternshipsListView />);
    await screen.findByText("Backend Intern");
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    expect(await screen.findByText(/isn't ready to publish/i)).toBeInTheDocument();
  });
});
