import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getInstitutionStudents: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/institution/students", () => ({
  getInstitutionStudents: mocks.getInstitutionStudents,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: mocks.push }),
  useSearchParams: () => new URLSearchParams(),
}));

import { StudentDirectory } from "@/components/institution/students/student-directory";
import { ApiError } from "@/lib/api";
import type { StudentListResponse, StudentSummary } from "@/types/institution-student";

function student(overrides: Partial<StudentSummary> = {}): StudentSummary {
  return {
    id: "student-1",
    full_name: "Priya Sharma",
    username: "priya_s",
    avatar_url: null,
    link_request_id: "req-1",
    department_id: "dept-cse",
    department: "CSE",
    batch: 2026,
    cgpa: 8.7,
    percentage: null,
    placement_status: "PLACED",
    internship_status: "NONE",
    top_skills: ["Python", "React"],
    profile_completion: 80,
    ...overrides,
  };
}

function response(overrides: Partial<StudentListResponse> = {}): StudentListResponse {
  return {
    students: [student()],
    total: 1,
    page: 1,
    page_size: 20,
    filters: { departments: [{ id: "dept-cse", name: "CSE" }], batches: [2026] },
    summary: { total_students: 1, placed: 1, unplaced: 0, no_applications: 0, internship_selected: 0 },
    ...overrides,
  };
}

describe("StudentDirectory", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches students on mount", () => {
    mocks.getInstitutionStudents.mockReturnValue(new Promise(() => {}));
    render(<StudentDirectory />);
    expect(mocks.getInstitutionStudents).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getInstitutionStudents.mockReturnValue(new Promise(() => {}));
    render(<StudentDirectory />);
    expect(screen.getByText(/Loading students/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getInstitutionStudents.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<StudentDirectory />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows an empty state for an institution with no linked students", async () => {
    mocks.getInstitutionStudents.mockResolvedValueOnce(
      response({ students: [], total: 0, filters: { departments: [], batches: [] } }),
    );
    render(<StudentDirectory />);
    expect(await screen.findByText("No students are linked to this institution yet")).toBeInTheDocument();
  });

  it("renders summary cards from the roster-wide summary", async () => {
    mocks.getInstitutionStudents.mockResolvedValueOnce(response());
    render(<StudentDirectory />);
    expect(await screen.findByText("Total Students")).toBeInTheDocument();
    expect(screen.getAllByText("1").length).toBeGreaterThan(0);
  });

  it("renders the student row with placement and internship badges", async () => {
    mocks.getInstitutionStudents.mockResolvedValueOnce(response());
    render(<StudentDirectory />);
    expect(await screen.findByText("Priya Sharma")).toBeInTheDocument();
    // "Placed" also appears as a summary-card label, so this row must
    // add at least one more occurrence (the badge) on top of that.
    expect(screen.getAllByText("Placed").length).toBeGreaterThanOrEqual(2);
    expect(screen.getByText("None")).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("navigates to the student detail page when a row is clicked", async () => {
    mocks.getInstitutionStudents.mockResolvedValueOnce(response());
    render(<StudentDirectory />);
    await userEvent.click(await screen.findByRole("button", { name: "View" }));
    expect(mocks.push).toHaveBeenCalledWith("/institution/students/student-1");
  });

  it("re-fetches with the search term after debounce", async () => {
    mocks.getInstitutionStudents.mockResolvedValue(response());
    render(<StudentDirectory />);
    await screen.findByText("Priya Sharma");

    await userEvent.type(screen.getByLabelText(/search students/i), "priya");

    await waitFor(
      () =>
        expect(mocks.getInstitutionStudents).toHaveBeenLastCalledWith(
          expect.objectContaining({ search: "priya" }),
        ),
      { timeout: 2000 },
    );
  });

  it("shows a no-results empty state distinct from the no-students-linked state", async () => {
    mocks.getInstitutionStudents.mockResolvedValue(
      response({ students: [], total: 0, summary: { total_students: 5, placed: 1, unplaced: 2, no_applications: 2, internship_selected: 0 } }),
    );
    render(<StudentDirectory />);
    await userEvent.type(screen.getByLabelText(/search students/i), "nomatch");
    expect(await screen.findByText("No students match your filters")).toBeInTheDocument();
  });

  it("shows pagination info and disables Previous on the first page", async () => {
    mocks.getInstitutionStudents.mockResolvedValueOnce(
      response({ total: 45, page: 1, page_size: 20, students: [student()] }),
    );
    render(<StudentDirectory />);
    expect(await screen.findByText(/Showing 1-20 of 45 students/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Previous" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Next" })).not.toBeDisabled();
  });
});
