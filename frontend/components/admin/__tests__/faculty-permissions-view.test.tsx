import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const {
  listFacultyAssessmentPermissions,
  grantAssessmentCapability,
  setAssessmentPermissionStatus,
  listFacultyMentorPermissions,
  grantMentorCapability,
  setMentorPermissionStatus,
} = vi.hoisted(() => ({
  listFacultyAssessmentPermissions: vi.fn(),
  grantAssessmentCapability: vi.fn(),
  setAssessmentPermissionStatus: vi.fn(),
  listFacultyMentorPermissions: vi.fn(),
  grantMentorCapability: vi.fn(),
  setMentorPermissionStatus: vi.fn(),
}));

vi.mock("@/lib/admin/faculty-permissions", () => ({
  listFacultyAssessmentPermissions,
  grantAssessmentCapability,
  setAssessmentPermissionStatus,
}));

vi.mock("@/lib/admin/mentor-permissions", () => ({
  listFacultyMentorPermissions,
  grantMentorCapability,
  setMentorPermissionStatus,
}));

import { FacultyPermissionsView } from "@/components/admin/faculty-permissions-view";

function facultyMember(overrides = {}) {
  return {
    faculty_id: "faculty-1",
    email: "faculty@example.com",
    username: "faculty1",
    full_name: "Dr. Faculty",
    permissions: [],
    ...overrides,
  };
}

function mentorFacultyEntry(overrides = {}) {
  return {
    faculty_id: "faculty-1",
    email: "faculty@example.com",
    username: "faculty1",
    full_name: "Dr. Faculty",
    permission: null,
    ...overrides,
  };
}

describe("FacultyPermissionsView (mentor capability section)", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows an ungranted mentor capability with a Grant action", async () => {
    listFacultyAssessmentPermissions.mockResolvedValue({ faculty: [facultyMember()] });
    listFacultyMentorPermissions.mockResolvedValue({ faculty: [mentorFacultyEntry()] });
    render(<FacultyPermissionsView />);

    expect(await screen.findByText("faculty_mentor")).toBeInTheDocument();
    const row = screen.getByText("faculty_mentor").closest("div")!.parentElement!;
    expect(row).toHaveTextContent("Not granted");
    expect(screen.getAllByRole("button", { name: "Grant" }).length).toBeGreaterThan(0);
  });

  it("grants the mentor capability", async () => {
    listFacultyAssessmentPermissions.mockResolvedValue({ faculty: [facultyMember()] });
    listFacultyMentorPermissions
      .mockResolvedValueOnce({ faculty: [mentorFacultyEntry()] })
      .mockResolvedValueOnce({
        faculty: [
          mentorFacultyEntry({
            permission: {
              permission_id: "mentor-perm-1",
              status: "GRANTED",
              granted_by: "admin-1",
              status_changed_by: "admin-1",
              created_at: "2026-01-01T00:00:00Z",
              updated_at: "2026-01-01T00:00:00Z",
            },
          }),
        ],
      });
    grantMentorCapability.mockResolvedValue({});
    render(<FacultyPermissionsView />);

    await screen.findByText("faculty_mentor");
    const mentorRow = screen.getByText("faculty_mentor").closest("div")!.parentElement!;
    await userEvent.click(within(mentorRow).getByRole("button", { name: "Grant" }));

    await waitFor(() => expect(grantMentorCapability).toHaveBeenCalledWith("faculty-1"));
  });

  it("suspends and reinstates a granted mentor capability", async () => {
    const grantedPermission = {
      permission_id: "mentor-perm-1",
      status: "GRANTED",
      granted_by: "admin-1",
      status_changed_by: "admin-1",
      created_at: "2026-01-01T00:00:00Z",
      updated_at: "2026-01-01T00:00:00Z",
    };
    listFacultyAssessmentPermissions.mockResolvedValue({ faculty: [facultyMember()] });
    listFacultyMentorPermissions
      .mockResolvedValueOnce({ faculty: [mentorFacultyEntry({ permission: grantedPermission })] })
      .mockResolvedValueOnce({
        faculty: [mentorFacultyEntry({ permission: { ...grantedPermission, status: "SUSPENDED" } })],
      });
    setMentorPermissionStatus.mockResolvedValue({});
    render(<FacultyPermissionsView />);

    await screen.findByText("faculty_mentor");
    await userEvent.click(screen.getByRole("button", { name: "Suspend" }));

    await waitFor(() => expect(setMentorPermissionStatus).toHaveBeenCalledWith("mentor-perm-1", "SUSPENDED"));
  });
});
