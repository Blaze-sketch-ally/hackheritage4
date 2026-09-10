import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getPlacementDrive: vi.fn(),
  getPlacementDriveStudents: vi.fn(),
  getPlacementDriveApplicants: vi.fn(),
  updatePlacementDriveStatus: vi.fn(),
  updatePlacementDrive: vi.fn(),
  getAvailablePlacementJobs: vi.fn(),
  getInstitutionDepartments: vi.fn(),
}));

vi.mock("@/lib/institution/placements", () => ({
  getPlacementDrive: mocks.getPlacementDrive,
  getPlacementDriveStudents: mocks.getPlacementDriveStudents,
  getPlacementDriveApplicants: mocks.getPlacementDriveApplicants,
  updatePlacementDriveStatus: mocks.updatePlacementDriveStatus,
  updatePlacementDrive: mocks.updatePlacementDrive,
  getAvailablePlacementJobs: mocks.getAvailablePlacementJobs,
}));

vi.mock("@/lib/institution/departments", () => ({
  getInstitutionDepartments: mocks.getInstitutionDepartments,
}));

import { PlacementDriveDetail } from "@/components/institution/placements/placement-drive-detail";
import { ApiError } from "@/lib/api";
import type { PlacementDriveDetail as PlacementDriveDetailData } from "@/types/institution-placement";

function driveDetail(overrides: Partial<PlacementDriveDetailData> = {}): PlacementDriveDetailData {
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
    status: "DRAFT",
    application_deadline: "2026-03-01",
    drive_date: null,
    mode: "ONSITE",
    venue: null,
    description: null,
    instructions: null,
    job_description: "Build things.",
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

describe("PlacementDriveDetail", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches the drive on mount", () => {
    mocks.getPlacementDrive.mockReturnValue(new Promise(() => {}));
    render(<PlacementDriveDetail driveId="drive-1" />);
    expect(mocks.getPlacementDrive).toHaveBeenCalledWith("drive-1");
  });

  it("shows a loading state", () => {
    mocks.getPlacementDrive.mockReturnValue(new Promise(() => {}));
    render(<PlacementDriveDetail driveId="drive-1" />);
    expect(screen.getByText(/Loading placement drive/i)).toBeInTheDocument();
  });

  it("shows a not-found message for a 404", async () => {
    mocks.getPlacementDrive.mockRejectedValueOnce(new ApiError(404, "Placement drive not found."));
    render(<PlacementDriveDetail driveId="drive-1" />);
    expect(await screen.findByText("This placement drive was not found.")).toBeInTheDocument();
  });

  it("renders drive header, KPIs and job info", async () => {
    mocks.getPlacementDrive.mockResolvedValueOnce(driveDetail());
    mocks.getPlacementDriveStudents.mockReturnValue(new Promise(() => {}));
    render(<PlacementDriveDetail driveId="drive-1" />);

    expect(await screen.findByRole("heading", { name: "Campus Drive 2026" })).toBeInTheDocument();
    expect(screen.getByText(/Software Engineer/)).toBeInTheDocument();
    expect(screen.getByText(/Acme Corp/)).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("12")).toBeInTheDocument();
    expect(screen.getByText("5")).toBeInTheDocument();
  });

  it("shows 'no restrictions' when no eligibility criteria are set", async () => {
    mocks.getPlacementDrive.mockResolvedValueOnce(driveDetail());
    mocks.getPlacementDriveStudents.mockReturnValue(new Promise(() => {}));
    render(<PlacementDriveDetail driveId="drive-1" />);
    expect(
      await screen.findByText("No restrictions — every student linked to your institution is eligible."),
    ).toBeInTheDocument();
  });

  it("shows department/batch/CGPA/skill eligibility criteria when set", async () => {
    mocks.getPlacementDrive.mockResolvedValueOnce(
      driveDetail({
        eligible_department_names: ["CSE"],
        eligible_batches: [2026, 2027],
        minimum_cgpa: 7.5,
        eligible_skill_names: ["Python"],
      }),
    );
    mocks.getPlacementDriveStudents.mockReturnValue(new Promise(() => {}));
    render(<PlacementDriveDetail driveId="drive-1" />);

    expect(await screen.findByText("CSE")).toBeInTheDocument();
    expect(screen.getByText("2026, 2027")).toBeInTheDocument();
    expect(screen.getByText("7.5")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("shows only the transitions valid from the current status", async () => {
    mocks.getPlacementDrive.mockResolvedValueOnce(driveDetail({ status: "DRAFT" }));
    mocks.getPlacementDriveStudents.mockReturnValue(new Promise(() => {}));
    render(<PlacementDriveDetail driveId="drive-1" />);

    expect(await screen.findByRole("button", { name: /Mark Open/ })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Mark Cancelled/ })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Mark Completed/ })).not.toBeInTheDocument();
  });

  it("shows no transition buttons for a terminal status", async () => {
    mocks.getPlacementDrive.mockResolvedValueOnce(driveDetail({ status: "COMPLETED" }));
    mocks.getPlacementDriveStudents.mockReturnValue(new Promise(() => {}));
    render(<PlacementDriveDetail driveId="drive-1" />);
    await screen.findByRole("heading", { name: "Campus Drive 2026" });
    expect(screen.queryByRole("button", { name: /^Mark/ })).not.toBeInTheDocument();
  });

  it("advances the drive status and reflects it immediately", async () => {
    mocks.getPlacementDrive.mockResolvedValueOnce(driveDetail({ status: "DRAFT" }));
    mocks.getPlacementDriveStudents.mockReturnValue(new Promise(() => {}));
    mocks.updatePlacementDriveStatus.mockResolvedValueOnce(driveDetail({ status: "OPEN" }));
    render(<PlacementDriveDetail driveId="drive-1" />);

    await userEvent.click(await screen.findByRole("button", { name: /Mark Open/ }));
    await waitFor(() => expect(mocks.updatePlacementDriveStatus).toHaveBeenCalledWith("drive-1", "OPEN"));
    expect(await screen.findByText("Open")).toBeInTheDocument();
  });

  it("surfaces an error when an invalid transition is rejected", async () => {
    mocks.getPlacementDrive.mockResolvedValueOnce(driveDetail({ status: "DRAFT" }));
    mocks.getPlacementDriveStudents.mockReturnValue(new Promise(() => {}));
    mocks.updatePlacementDriveStatus.mockRejectedValueOnce(
      new ApiError(409, "This status change is not allowed."),
    );
    render(<PlacementDriveDetail driveId="drive-1" />);
    await userEvent.click(await screen.findByRole("button", { name: /Mark Open/ }));
    expect(await screen.findByText("This status change is not allowed.")).toBeInTheDocument();
  });

  it("loads eligible students by default, with reasons for ineligible ones", async () => {
    mocks.getPlacementDrive.mockResolvedValueOnce(driveDetail());
    mocks.getPlacementDriveStudents.mockResolvedValueOnce({
      eligible_count: 1,
      applied_count: 0,
      students: [
        {
          id: "s1",
          full_name: "Asha Rao",
          username: "asha",
          avatar_url: null,
          department: "CSE",
          batch: 2026,
          cgpa: 6.5,
          is_eligible: false,
          reasons: ["CGPA below 7.5"],
          application_status: null,
        },
      ],
    });
    render(<PlacementDriveDetail driveId="drive-1" />);

    expect(await screen.findByText("Asha Rao")).toBeInTheDocument();
    expect(screen.getByText("Not Eligible")).toBeInTheDocument();
    expect(screen.getByText("CGPA below 7.5")).toBeInTheDocument();
    expect(screen.getByText("Has not applied")).toBeInTheDocument();
  });

  it("switches to the applicants panel and shows real application/interview status", async () => {
    mocks.getPlacementDrive.mockResolvedValueOnce(driveDetail());
    mocks.getPlacementDriveStudents.mockResolvedValueOnce({ eligible_count: 0, applied_count: 0, students: [] });
    mocks.getPlacementDriveApplicants.mockResolvedValueOnce({
      applicants: [
        {
          application_id: "a1",
          student_id: "s1",
          full_name: "Asha Rao",
          username: "asha",
          department: "CSE",
          cgpa: 8.2,
          status: "INTERVIEW_SCHEDULED",
          applied_at: "2026-01-05",
          interview: { scheduled_at: "2026-02-01T10:00:00Z", mode: "ONLINE", status: "SCHEDULED" },
        },
      ],
    });
    render(<PlacementDriveDetail driveId="drive-1" />);
    await screen.findByRole("heading", { name: "Campus Drive 2026" });

    await userEvent.click(screen.getByRole("button", { name: "Applicants" }));
    expect(mocks.getPlacementDriveApplicants).toHaveBeenCalledWith("drive-1");
    expect(await screen.findByText("Asha Rao")).toBeInTheDocument();
    expect(screen.getByText("INTERVIEW_SCHEDULED")).toBeInTheDocument();
    expect(screen.getByText(/SCHEDULED · ONLINE/)).toBeInTheDocument();
  });

  it("opens the edit dialog with the job shown read-only", async () => {
    mocks.getPlacementDrive.mockResolvedValueOnce(driveDetail());
    mocks.getPlacementDriveStudents.mockReturnValue(new Promise(() => {}));
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [] });
    render(<PlacementDriveDetail driveId="drive-1" />);

    await userEvent.click(await screen.findByRole("button", { name: /Edit/ }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/Software Engineer/)).toBeInTheDocument();
    expect(within(dialog).getByText("The job a drive coordinates cannot be changed.")).toBeInTheDocument();
    expect(within(dialog).queryByRole("combobox", { name: "Job" })).not.toBeInTheDocument();
  });

  it("saves an edit and reflects the updated title", async () => {
    mocks.getPlacementDrive.mockResolvedValueOnce(driveDetail());
    mocks.getPlacementDriveStudents.mockReturnValue(new Promise(() => {}));
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [] });
    mocks.updatePlacementDrive.mockResolvedValueOnce(driveDetail({ title: "Updated Drive Title" }));
    render(<PlacementDriveDetail driveId="drive-1" />);

    await userEvent.click(await screen.findByRole("button", { name: /Edit/ }));
    const dialog = await screen.findByRole("dialog");
    const titleInput = within(dialog).getByLabelText("Drive Title");
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Updated Drive Title");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save Changes" }));

    expect(await screen.findByRole("heading", { name: "Updated Drive Title" })).toBeInTheDocument();
  });
});
