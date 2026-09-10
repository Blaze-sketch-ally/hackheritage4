import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getInstitutionDepartment: vi.fn(),
  updateInstitutionDepartment: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/institution/departments", () => ({
  getInstitutionDepartment: mocks.getInstitutionDepartment,
  updateInstitutionDepartment: mocks.updateInstitutionDepartment,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

import { DepartmentDetail } from "@/components/institution/departments/department-detail";
import { ApiError } from "@/lib/api";
import type { DepartmentDetail as DepartmentDetailData } from "@/types/institution-department";

function department(overrides: Partial<DepartmentDetailData> = {}): DepartmentDetailData {
  return {
    id: "dept-cse",
    name: "CSE",
    code: "CSE01",
    description: "Computer Science and Engineering",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    student_count: 10,
    placed_count: 6,
    unplaced_count: 3,
    no_applications_count: 1,
    placement_rate: 60,
    internship_selected_count: 2,
    ...overrides,
  };
}

describe("DepartmentDetail", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches the department on mount", () => {
    mocks.getInstitutionDepartment.mockReturnValue(new Promise(() => {}));
    render(<DepartmentDetail departmentId="dept-cse" />);
    expect(mocks.getInstitutionDepartment).toHaveBeenCalledWith("dept-cse");
  });

  it("shows a loading state", () => {
    mocks.getInstitutionDepartment.mockReturnValue(new Promise(() => {}));
    render(<DepartmentDetail departmentId="dept-cse" />);
    expect(screen.getByText(/Loading department/i)).toBeInTheDocument();
  });

  it("shows a not-found message for a 404", async () => {
    mocks.getInstitutionDepartment.mockRejectedValueOnce(new ApiError(404, "Department not found."));
    render(<DepartmentDetail departmentId="dept-cse" />);
    expect(await screen.findByText("This department was not found.")).toBeInTheDocument();
  });

  it("renders the overview and student metrics", async () => {
    mocks.getInstitutionDepartment.mockResolvedValueOnce(department());
    render(<DepartmentDetail departmentId="dept-cse" />);

    expect(await screen.findByRole("heading", { name: "CSE" })).toBeInTheDocument();
    expect(screen.getByText("Computer Science and Engineering", { exact: false })).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText("2")).toBeInTheDocument();
  });

  it("shows inactive status for a deactivated department without hiding its stats", async () => {
    mocks.getInstitutionDepartment.mockResolvedValueOnce(department({ is_active: false }));
    render(<DepartmentDetail departmentId="dept-cse" />);
    expect(await screen.findByText("Inactive")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
  });

  it("navigates to the student directory filtered by this department", async () => {
    mocks.getInstitutionDepartment.mockResolvedValueOnce(department());
    render(<DepartmentDetail departmentId="dept-cse" />);
    await userEvent.click(await screen.findByRole("button", { name: "View students in this department" }));
    expect(mocks.push).toHaveBeenCalledWith("/institution/students?department=dept-cse");
  });

  it("opens the edit dialog pre-filled and saves changes", async () => {
    mocks.getInstitutionDepartment.mockResolvedValueOnce(department());
    mocks.updateInstitutionDepartment.mockResolvedValueOnce(department({ name: "Computer Science" }));
    render(<DepartmentDetail departmentId="dept-cse" />);
    await screen.findByRole("heading", { name: "CSE" });

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByLabelText("Name")).toHaveValue("CSE");

    await userEvent.clear(within(dialog).getByLabelText("Name"));
    await userEvent.type(within(dialog).getByLabelText("Name"), "Computer Science");
    await userEvent.click(within(dialog).getByRole("button", { name: "Save Changes" }));

    expect(await screen.findByRole("heading", { name: "Computer Science" })).toBeInTheDocument();
  });
});
