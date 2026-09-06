import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getInternship: vi.fn(),
  updateInternship: vi.fn(),
  publishInternship: vi.fn(),
  closeInternship: vi.fn(),
  archiveInternship: vi.fn(),
  getSkillCatalog: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/internships", () => ({
  getInternship: mocks.getInternship,
  updateInternship: mocks.updateInternship,
  publishInternship: mocks.publishInternship,
  closeInternship: mocks.closeInternship,
  archiveInternship: mocks.archiveInternship,
}));
vi.mock("@/lib/industry/skills", () => ({ getSkillCatalog: mocks.getSkillCatalog }));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { InternshipDetailView } from "@/components/industry/internships/internship-detail-view";
import { ApiError } from "@/lib/api";
import type { Internship } from "@/types/internship";

function internship(overrides: Partial<Internship> = {}): Internship {
  return {
    id: "int-1",
    industry_id: "industry-1",
    title: "Backend Intern",
    description: "Work on APIs.",
    location: "Pune",
    work_mode: "HYBRID",
    duration_months: 6,
    stipend_amount: 15000,
    stipend_currency: "INR",
    openings: 2,
    eligibility_criteria: null,
    application_deadline: "2026-12-01",
    start_date: null,
    status: "DRAFT",
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

describe("InternshipDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getInternship.mockReturnValue(new Promise(() => {}));
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    render(<InternshipDetailView internshipId="int-1" />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows a not-found message on a 404", async () => {
    mocks.getInternship.mockRejectedValueOnce(new ApiError(404, "Internship not found."));
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    render(<InternshipDetailView internshipId="int-x" />);
    expect(await screen.findByText(/doesn't exist or isn't yours/i)).toBeInTheDocument();
  });

  it("renders internship detail with status and skills", async () => {
    mocks.getInternship.mockResolvedValueOnce(internship());
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    render(<InternshipDetailView internshipId="int-1" />);

    expect(await screen.findByRole("heading", { name: "Backend Intern" })).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Required Skills (1)")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("switches to the edit form and saves changes", async () => {
    mocks.getInternship.mockResolvedValueOnce(internship());
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    mocks.updateInternship.mockResolvedValueOnce(internship({ title: "Backend Intern (updated)" }));

    render(<InternshipDetailView internshipId="int-1" />);
    await screen.findByRole("heading", { name: "Backend Intern" });

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const title = await screen.findByLabelText("Title");
    await userEvent.clear(title);
    await userEvent.type(title, "Backend Intern (updated)");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(mocks.updateInternship).toHaveBeenCalledTimes(1));
    expect(mocks.updateInternship.mock.calls[0][0]).toBe("int-1");
    expect(await screen.findByText("Changes saved.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Backend Intern (updated)" })).toBeInTheDocument();
  });

  it("publishes via the confirmation dialog", async () => {
    mocks.getInternship.mockResolvedValueOnce(internship());
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    mocks.publishInternship.mockResolvedValueOnce(internship({ status: "PUBLISHED" }));

    render(<InternshipDetailView internshipId="int-1" />);
    await screen.findByRole("heading", { name: "Backend Intern" });

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishInternship).toHaveBeenCalledWith("int-1"));
    expect(await screen.findByText("Internship published.")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("starts in edit mode when initialEdit is set", async () => {
    mocks.getInternship.mockResolvedValueOnce(internship());
    mocks.getSkillCatalog.mockResolvedValue({ skills: [] });
    render(<InternshipDetailView internshipId="int-1" initialEdit />);

    expect(await screen.findByRole("heading", { name: "Edit Internship" })).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Backend Intern");
  });
});
