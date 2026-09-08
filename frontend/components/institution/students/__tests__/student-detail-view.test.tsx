import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getInstitutionStudent: vi.fn(),
  unlinkStudent: vi.fn(),
  getInstitutionDepartments: vi.fn(),
  assignStudentDepartment: vi.fn(),
}));

vi.mock("@/lib/institution/students", () => ({
  getInstitutionStudent: mocks.getInstitutionStudent,
}));

vi.mock("@/lib/institution-links", () => ({
  unlinkStudent: mocks.unlinkStudent,
}));

vi.mock("@/lib/institution/departments", () => ({
  getInstitutionDepartments: mocks.getInstitutionDepartments,
  assignStudentDepartment: mocks.assignStudentDepartment,
}));

import { StudentDetailView } from "@/components/institution/students/student-detail-view";
import { ApiError } from "@/lib/api";
import type { StudentDetail } from "@/types/institution-student";

function detail(overrides: Partial<StudentDetail> = {}): StudentDetail {
  return {
    id: "student-1",
    full_name: "Priya Sharma",
    username: "priya_s",
    avatar_url: null,
    link_request_id: "req-1",
    department_id: "dept-cse",
    department: "CSE",
    self_reported_department: "CSE",
    batch: 2026,
    degree: "B.Tech",
    cgpa: 8.7,
    percentage: null,
    profile_completion: 80,
    skills: [{ skill_name: "Python", proficiency_level: "Advanced", is_verified: true }],
    projects: [
      {
        id: "p1",
        title: "Portfolio Site",
        description: "A personal site.",
        project_url: null,
        repo_url: "https://github.com/example/repo",
        is_ongoing: false,
        skills: ["React"],
      },
    ],
    certifications: [],
    achievements: [],
    applications: [
      {
        id: "a1",
        opportunity_type: "JOB",
        opportunity_title: "Backend Engineer",
        company_name: "Acme Corp",
        status: "SELECTED",
        applied_at: "2026-01-01",
      },
    ],
    placement_status: "PLACED",
    internship_status: "NONE",
    assessments_completed: 1,
    average_assessment_percentage: 80,
    assessments: [
      { assessment_title: "Python Basics", skill_name: "Python", status: "COMPLETED", percentage: 80, submitted_at: "2026-01-01" },
    ],
    interviews: [],
    notes: ["No resume/file storage exists in this schema."],
    ...overrides,
  };
}

describe("StudentDetailView", () => {
  beforeEach(() => {
    mocks.getInstitutionDepartments.mockResolvedValue({
      departments: [
        { id: "dept-cse", name: "CSE", code: "CSE", description: null, is_active: true, created_at: null,
          updated_at: null, student_count: 0, placed_count: 0, unplaced_count: 0, no_applications_count: 0,
          placement_rate: null, internship_selected_count: 0 },
        { id: "dept-ece", name: "ECE", code: "ECE", description: null, is_active: true, created_at: null,
          updated_at: null, student_count: 0, placed_count: 0, unplaced_count: 0, no_applications_count: 0,
          placement_rate: null, internship_selected_count: 0 },
      ],
    });
  });

  afterEach(() => vi.resetAllMocks());

  it("fetches the student on mount", () => {
    mocks.getInstitutionStudent.mockReturnValue(new Promise(() => {}));
    render(<StudentDetailView studentId="student-1" />);
    expect(mocks.getInstitutionStudent).toHaveBeenCalledWith("student-1");
  });

  it("shows a loading state", () => {
    mocks.getInstitutionStudent.mockReturnValue(new Promise(() => {}));
    render(<StudentDetailView studentId="student-1" />);
    expect(screen.getByText(/Loading student/i)).toBeInTheDocument();
  });

  it("shows a not-found message for a 404", async () => {
    mocks.getInstitutionStudent.mockRejectedValueOnce(new ApiError(404, "Student not found."));
    render(<StudentDetailView studentId="student-1" />);
    expect(
      await screen.findByText(/not found, or is not linked to your institution/i),
    ).toBeInTheDocument();
  });

  it("renders the profile header, academics, skills, applications and assessments", async () => {
    mocks.getInstitutionStudent.mockResolvedValueOnce(detail());
    render(<StudentDetailView studentId="student-1" />);

    expect(await screen.findByRole("heading", { name: "Priya Sharma" })).toBeInTheDocument();
    expect(screen.getByText("8.70")).toBeInTheDocument();
    expect(screen.getByText(/Python · Advanced/)).toBeInTheDocument();
    expect(screen.getByText("Backend Engineer")).toBeInTheDocument();
    expect(screen.getByText("Portfolio Site")).toBeInTheDocument();
    expect(screen.getByText(/Python Basics/)).toBeInTheDocument();
  });

  it("shows empty states for sections with no data", async () => {
    mocks.getInstitutionStudent.mockResolvedValueOnce(
      detail({ applications: [], projects: [], certifications: [], achievements: [], interviews: [] }),
    );
    render(<StudentDetailView studentId="student-1" />);
    await screen.findByRole("heading", { name: "Priya Sharma" });
    expect(screen.getByText("No applications yet")).toBeInTheDocument();
    expect(screen.getByText("No portfolio items yet")).toBeInTheDocument();
    expect(screen.getByText("No interviews on record")).toBeInTheDocument();
  });

  it("surfaces the schema-limitation notes", async () => {
    mocks.getInstitutionStudent.mockResolvedValueOnce(detail());
    render(<StudentDetailView studentId="student-1" />);
    expect(
      await screen.findByText("No resume/file storage exists in this schema."),
    ).toBeInTheDocument();
  });

  it("unlinks the student through the confirmation dialog", async () => {
    mocks.getInstitutionStudent.mockResolvedValueOnce(detail());
    mocks.unlinkStudent.mockResolvedValueOnce({});
    render(<StudentDetailView studentId="student-1" />);

    await userEvent.click(await screen.findByRole("button", { name: /unlink student/i }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Unlink" }));

    expect(mocks.unlinkStudent).toHaveBeenCalledWith("req-1");
    expect(await screen.findByText("Student unlinked")).toBeInTheDocument();
  });

  it("does not show an unlink action when there is no link_request_id", async () => {
    mocks.getInstitutionStudent.mockResolvedValueOnce(detail({ link_request_id: null }));
    render(<StudentDetailView studentId="student-1" />);
    await screen.findByRole("heading", { name: "Priya Sharma" });
    expect(screen.queryByRole("button", { name: /unlink student/i })).not.toBeInTheDocument();
  });

  it("shows the department selector, enabled once departments load, with the self-reported value alongside it", async () => {
    mocks.getInstitutionStudent.mockResolvedValueOnce(detail());
    render(<StudentDetailView studentId="student-1" />);
    await screen.findByRole("heading", { name: "Priya Sharma" });

    const select = await screen.findByLabelText("Department");
    expect(select).toBeEnabled();
    expect(screen.getByText(/Student's own profile lists: "CSE"/)).toBeInTheDocument();
  });

});
