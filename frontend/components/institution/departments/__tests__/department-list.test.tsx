import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getInstitutionDepartments: vi.fn(),
  createInstitutionDepartment: vi.fn(),
  updateInstitutionDepartment: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/institution/departments", () => ({
  getInstitutionDepartments: mocks.getInstitutionDepartments,
  createInstitutionDepartment: mocks.createInstitutionDepartment,
  updateInstitutionDepartment: mocks.updateInstitutionDepartment,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
}));

import { DepartmentList } from "@/components/institution/departments/department-list";
import { ApiError } from "@/lib/api";
import type { DepartmentSummary } from "@/types/institution-department";

function department(overrides: Partial<DepartmentSummary> = {}): DepartmentSummary {
  return {
    id: "dept-cse",
    name: "CSE",
    code: "CSE01",
    description: null,
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

describe("DepartmentList", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches departments on mount", () => {
    mocks.getInstitutionDepartments.mockReturnValue(new Promise(() => {}));
    render(<DepartmentList />);
    expect(mocks.getInstitutionDepartments).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getInstitutionDepartments.mockReturnValue(new Promise(() => {}));
    render(<DepartmentList />);
    expect(screen.getByText(/Loading departments/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getInstitutionDepartments.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<DepartmentList />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows an empty state with an Add Department action when there are none", async () => {
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [] });
    render(<DepartmentList />);
    expect(await screen.findByText("No departments yet")).toBeInTheDocument();
  });

  it("lists departments with student/placement stats", async () => {
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [department()] });
    render(<DepartmentList />);

    expect(await screen.findByText("CSE")).toBeInTheDocument();
    expect(screen.getByText("10")).toBeInTheDocument();
    expect(screen.getByText("6")).toBeInTheDocument();
    expect(screen.getByText("60%")).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
  });

  it("shows a no-results state when the search matches nothing", async () => {
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [department()] });
    render(<DepartmentList />);
    await screen.findByText("CSE");

    await userEvent.type(screen.getByLabelText("Search departments"), "mechanical");
    expect(await screen.findByText("No departments match your filters")).toBeInTheDocument();
  });

  it("search matches by code as well as name", async () => {
    mocks.getInstitutionDepartments.mockResolvedValueOnce({
      departments: [department(), department({ id: "dept-ece", name: "Electronics", code: "ECE" })],
    });
    render(<DepartmentList />);
    await screen.findByText("CSE");

    await userEvent.type(screen.getByLabelText("Search departments"), "ece");
    expect(await screen.findByText("Electronics")).toBeInTheDocument();
    expect(screen.queryByText("CSE")).not.toBeInTheDocument();
  });

  it("opens the create dialog and submits a new department", async () => {
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [] });
    // Saving reloads the list -- queue the post-save refetch too.
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [department({ name: "Mechanical" })] });
    mocks.createInstitutionDepartment.mockResolvedValueOnce(department({ name: "Mechanical" }));
    render(<DepartmentList />);
    await screen.findByText("No departments yet");

    // Both the header action and the empty-state action are labeled
    // "Add Department" while the list is empty -- either opens the same
    // dialog, so the first match is fine here.
    await userEvent.click(screen.getAllByRole("button", { name: "Add Department" })[0]);
    const dialog = await screen.findByRole("dialog");
    await userEvent.type(within(dialog).getByLabelText("Name"), "Mechanical");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add Department" }));

    await waitFor(() =>
      expect(mocks.createInstitutionDepartment).toHaveBeenCalledWith({
        name: "Mechanical",
        code: null,
        description: null,
      }),
    );
  });

  it("blocks submit with a blank name", async () => {
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [] });
    render(<DepartmentList />);
    await screen.findByText("No departments yet");

    await userEvent.click(screen.getAllByRole("button", { name: "Add Department" })[0]);
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Add Department" }));

    expect(await screen.findByText("Department name is required.")).toBeInTheDocument();
    expect(mocks.createInstitutionDepartment).not.toHaveBeenCalled();
  });

  it("surfaces a duplicate-name error from the API", async () => {
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [department()] });
    mocks.createInstitutionDepartment.mockRejectedValueOnce(
      new ApiError(409, "A department with that name already exists."),
    );
    render(<DepartmentList />);
    await screen.findByText("CSE");

    await userEvent.click(screen.getByRole("button", { name: "Add Department" }));
    await userEvent.type(screen.getByLabelText("Name"), "CSE");
    await userEvent.click(screen.getByRole("button", { name: "Add Department" }));

    expect(
      await screen.findByText("A department with that name already exists."),
    ).toBeInTheDocument();
  });

  it("opens the edit dialog pre-filled and saves changes", async () => {
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [department()] });
    // Saving reloads the list -- queue the post-save refetch too.
    mocks.getInstitutionDepartments.mockResolvedValueOnce({
      departments: [department({ description: "Updated description" })],
    });
    mocks.updateInstitutionDepartment.mockResolvedValueOnce(
      department({ description: "Updated description" }),
    );
    render(<DepartmentList />);
    await screen.findByText("CSE");

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    expect(screen.getByLabelText("Name")).toHaveValue("CSE");

    await userEvent.type(screen.getByLabelText("Description (optional)"), "Updated description");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() =>
      expect(mocks.updateInstitutionDepartment).toHaveBeenCalledWith(
        "dept-cse",
        expect.objectContaining({ description: "Updated description" }),
      ),
    );
  });

  it("navigates to the department detail page when a row name is clicked", async () => {
    mocks.getInstitutionDepartments.mockResolvedValueOnce({ departments: [department()] });
    render(<DepartmentList />);
    await userEvent.click(await screen.findByText("CSE"));
    expect(mocks.push).toHaveBeenCalledWith("/institution/departments/dept-cse");
  });
});
