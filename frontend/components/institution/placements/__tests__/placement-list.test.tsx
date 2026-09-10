import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getPlacementDrives: vi.fn(),
  getPlacementOverview: vi.fn(),
  getAvailablePlacementJobs: vi.fn(),
  getInstitutionDepartments: vi.fn(),
  getSkillCatalog: vi.fn(),
  createPlacementDrive: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/institution/placements", () => ({
  getPlacementDrives: mocks.getPlacementDrives,
  getPlacementOverview: mocks.getPlacementOverview,
  getAvailablePlacementJobs: mocks.getAvailablePlacementJobs,
  createPlacementDrive: mocks.createPlacementDrive,
}));

vi.mock("@/lib/institution/departments", () => ({
  getInstitutionDepartments: mocks.getInstitutionDepartments,
}));

vi.mock("@/lib/industry/skills", () => ({
  getSkillCatalog: mocks.getSkillCatalog,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

import { PlacementList } from "@/components/institution/placements/placement-list";
import { ApiError } from "@/lib/api";
import type { PlacementDriveSummary, PlacementOverviewResponse } from "@/types/institution-placement";

function drive(overrides: Partial<PlacementDriveSummary> = {}): PlacementDriveSummary {
  return {
    id: "drive-1",
    job_id: "job-1",
    job_title: "Software Engineer",
    company_name: "Acme Corp",
    location: "Remote",
    work_mode: "REMOTE",
    employment_type: "FULL_TIME",
    salary_min: null,
    salary_max: null,
    salary_currency: "INR",
    job_status: "PUBLISHED",
    title: "Campus Drive 2026",
    status: "OPEN",
    application_deadline: "2026-03-01",
    drive_date: null,
    mode: "ONSITE",
    venue: null,
    eligible_department_ids: [],
    eligible_department_names: [],
    eligible_batches: [],
    minimum_cgpa: null,
    eligible_skill_ids: [],
    eligible_skill_names: [],
    eligible_count: 12,
    applied_count: 5,
    selected_count: 2,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function overview(overrides: Partial<PlacementOverviewResponse> = {}): PlacementOverviewResponse {
  return {
    active_drives: 1,
    completed_drives: 0,
    participating_students: 9,
    placed_students: 3,
    total_selected_offers: 3,
    placement_rate: 40,
    department_breakdown: [],
    company_breakdown: [],
    ...overrides,
  };
}

describe("PlacementList", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches drives and the overview on mount", () => {
    mocks.getPlacementDrives.mockReturnValue(new Promise(() => {}));
    mocks.getPlacementOverview.mockReturnValue(new Promise(() => {}));
    render(<PlacementList />);
    expect(mocks.getPlacementDrives).toHaveBeenCalledTimes(1);
    expect(mocks.getPlacementOverview).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getPlacementDrives.mockReturnValue(new Promise(() => {}));
    mocks.getPlacementOverview.mockReturnValue(new Promise(() => {}));
    render(<PlacementList />);
    expect(screen.getByText(/Loading placement drives/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getPlacementDrives.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    mocks.getPlacementOverview.mockResolvedValueOnce(overview());
    render(<PlacementList />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows an empty state with a New Drive action when there are none", async () => {
    mocks.getPlacementDrives.mockResolvedValueOnce({ drives: [] });
    mocks.getPlacementOverview.mockResolvedValueOnce(overview({ active_drives: 0 }));
    render(<PlacementList />);
    expect(await screen.findByText("No placement drives yet")).toBeInTheDocument();
  });

  it("renders drives with real application/selection counts", async () => {
    mocks.getPlacementDrives.mockResolvedValueOnce({ drives: [drive()] });
    mocks.getPlacementOverview.mockResolvedValueOnce(overview());
    render(<PlacementList />);

    expect(await screen.findByText("Campus Drive 2026")).toBeInTheDocument();
    expect(screen.getByText("Acme Corp")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("renders the drive-scoped KPI cards from the overview endpoint", async () => {
    mocks.getPlacementDrives.mockResolvedValueOnce({ drives: [drive()] });
    mocks.getPlacementOverview.mockResolvedValueOnce(overview());
    render(<PlacementList />);

    expect(await screen.findByText("Active Drives")).toBeInTheDocument();
    expect(screen.getByText("Placed Students")).toBeInTheDocument();
    expect(screen.getByText("40%")).toBeInTheDocument();
  });

  it("filters the list by search text", async () => {
    mocks.getPlacementDrives.mockResolvedValue({ drives: [drive()] });
    mocks.getPlacementOverview.mockResolvedValueOnce(overview());
    render(<PlacementList />);
    await screen.findByText("Campus Drive 2026");

    await userEvent.type(screen.getByLabelText("Search placement drives"), "acme");
    await waitFor(() =>
      expect(mocks.getPlacementDrives).toHaveBeenLastCalledWith(
        expect.objectContaining({ search: "acme" }),
      ),
    );
  });

  it("navigates to the drive detail page when a row is clicked", async () => {
    mocks.getPlacementDrives.mockResolvedValueOnce({ drives: [drive()] });
    mocks.getPlacementOverview.mockResolvedValueOnce(overview());
    render(<PlacementList />);
    await userEvent.click(await screen.findByText("Campus Drive 2026"));
    expect(mocks.push).toHaveBeenCalledWith("/institution/placements/drive-1");
  });

  it("opens the create-drive dialog", async () => {
    mocks.getPlacementDrives.mockResolvedValueOnce({ drives: [] });
    mocks.getPlacementOverview.mockResolvedValueOnce(overview({ active_drives: 0 }));
    mocks.getAvailablePlacementJobs.mockResolvedValueOnce({ jobs: [] });
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [] });
    render(<PlacementList />);
    await screen.findByText("No placement drives yet");

    await userEvent.click(screen.getAllByRole("button", { name: "New Drive" })[0]);
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText("New Placement Drive")).toBeInTheDocument();
    expect(mocks.getAvailablePlacementJobs).toHaveBeenCalled();
  });

  it("requires a job to be chosen before creating a drive", async () => {
    mocks.getPlacementDrives.mockResolvedValueOnce({ drives: [] });
    mocks.getPlacementOverview.mockResolvedValueOnce(overview({ active_drives: 0 }));
    mocks.getAvailablePlacementJobs.mockResolvedValueOnce({ jobs: [] });
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [] });
    render(<PlacementList />);
    await userEvent.click((await screen.findAllByRole("button", { name: "New Drive" }))[0]);
    const dialog = await screen.findByRole("dialog");

    await userEvent.type(
      await screen.findByPlaceholderText(/Campus Drive/i),
      "My Drive",
    );
    const submit = Array.from(dialog.querySelectorAll("button")).find(
      (b) => b.textContent === "Create Drive",
    ) as HTMLButtonElement;
    await userEvent.click(submit);

    expect(await screen.findByText("Choose a job for this drive to coordinate.")).toBeInTheDocument();
    expect(mocks.createPlacementDrive).not.toHaveBeenCalled();
  });
});
