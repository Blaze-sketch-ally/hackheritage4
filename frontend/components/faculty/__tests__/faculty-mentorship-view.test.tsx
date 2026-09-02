import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const {
  listMyMentorships,
  requestMentorship,
  updateMentorshipStatus,
  getMenteeProfile,
  getMentorshipNote,
  saveMentorshipNote,
  useMentorCapability,
} = vi.hoisted(() => ({
  listMyMentorships: vi.fn(),
  requestMentorship: vi.fn(),
  updateMentorshipStatus: vi.fn(),
  getMenteeProfile: vi.fn(),
  getMentorshipNote: vi.fn(),
  saveMentorshipNote: vi.fn(),
  useMentorCapability: vi.fn(),
}));

vi.mock("@/lib/faculty/mentorships", () => ({
  listMyMentorships,
  requestMentorship,
  updateMentorshipStatus,
  getMenteeProfile,
  getMentorshipNote,
  saveMentorshipNote,
}));

vi.mock("@/lib/faculty/mentor-capability", () => ({
  useMentorCapability,
}));

import { FacultyMentorshipView } from "@/components/faculty/faculty-mentorship-view";
import { ApiError } from "@/lib/api";

function mentorship(overrides = {}) {
  return {
    id: "mentorship-1",
    faculty_id: "faculty-1",
    student_id: "student-1",
    requested_by: "faculty-1",
    status: "REQUESTED",
    focus_area: "Career guidance",
    start_date: null,
    end_date: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function bundle(overrides = {}) {
  return {
    mentorship_id: "mentorship-1",
    student_id: "student-1",
    full_name: "Jane Student",
    email: "jane@example.com",
    username: "jane",
    academic_profile: {
      institution_name: "State University",
      department: "CS",
      degree: "B.Tech",
      graduation_year: 2027,
      cgpa: 8.5,
      percentage: null,
      career_goals: null,
      preferred_roles: [],
      interests: [],
    },
    skills: [],
    assessment_attempts: [],
    projects: [],
    certifications: [],
    ...overrides,
  };
}

describe("FacultyMentorshipView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("shows a disabled request form and a hint when the capability is not granted", async () => {
    useMentorCapability.mockReturnValue({ status: "ready", canMentor: false });
    listMyMentorships.mockResolvedValue({ mentorships: [] });
    render(<FacultyMentorshipView />);

    expect(await screen.findByText(/must grant you the mentor capability/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /request mentorship/i })).toBeDisabled();
  });

  it("requests a mentorship when the capability is granted", async () => {
    useMentorCapability.mockReturnValue({ status: "ready", canMentor: true });
    listMyMentorships.mockResolvedValue({ mentorships: [] });
    requestMentorship.mockResolvedValue(mentorship());
    render(<FacultyMentorshipView />);

    await waitFor(() => expect(listMyMentorships).toHaveBeenCalled());
    await userEvent.type(screen.getByLabelText("Student ID"), "student-1");
    await userEvent.click(screen.getByRole("button", { name: /request mentorship/i }));

    await waitFor(() => expect(requestMentorship).toHaveBeenCalledWith("student-1", null));
  });

  it("shows Withdraw for a request the caller made", async () => {
    useMentorCapability.mockReturnValue({ status: "ready", canMentor: true });
    listMyMentorships.mockResolvedValue({ mentorships: [mentorship({ requested_by: "faculty-1" })] });
    updateMentorshipStatus.mockResolvedValue(mentorship({ status: "WITHDRAWN" }));
    render(<FacultyMentorshipView />);

    expect(await screen.findByRole("button", { name: "Withdraw" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Accept" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Withdraw" }));
    await waitFor(() => expect(updateMentorshipStatus).toHaveBeenCalledWith("mentorship-1", "WITHDRAWN"));
  });

  it("shows Accept/Decline for a request the student made", async () => {
    useMentorCapability.mockReturnValue({ status: "ready", canMentor: true });
    listMyMentorships.mockResolvedValue({
      mentorships: [mentorship({ requested_by: "student-1" })],
    });
    updateMentorshipStatus.mockResolvedValue(mentorship({ status: "ACCEPTED" }));
    render(<FacultyMentorshipView />);

    expect(await screen.findByRole("button", { name: "Accept" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Decline" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Withdraw" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(updateMentorshipStatus).toHaveBeenCalledWith("mentorship-1", "ACCEPTED"));
  });

  it("shows Activate for an ACCEPTED mentorship", async () => {
    useMentorCapability.mockReturnValue({ status: "ready", canMentor: true });
    listMyMentorships.mockResolvedValue({ mentorships: [mentorship({ status: "ACCEPTED" })] });
    updateMentorshipStatus.mockResolvedValue(mentorship({ status: "ACTIVE" }));
    render(<FacultyMentorshipView />);

    await userEvent.click(await screen.findByRole("button", { name: "Activate" }));
    await waitFor(() => expect(updateMentorshipStatus).toHaveBeenCalledWith("mentorship-1", "ACTIVE"));
  });

  it("shows Complete/End and a View mentee toggle for an ACTIVE mentorship", async () => {
    useMentorCapability.mockReturnValue({ status: "ready", canMentor: true });
    listMyMentorships.mockResolvedValue({ mentorships: [mentorship({ status: "ACTIVE" })] });
    render(<FacultyMentorshipView />);

    expect(await screen.findByRole("button", { name: "Complete" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "End" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /view mentee/i })).toBeInTheDocument();
  });

  it("loads and displays the mentee bundle and private note when expanded", async () => {
    useMentorCapability.mockReturnValue({ status: "ready", canMentor: true });
    listMyMentorships.mockResolvedValue({ mentorships: [mentorship({ status: "ACTIVE" })] });
    getMenteeProfile.mockResolvedValue(bundle());
    getMentorshipNote.mockResolvedValue({
      id: "note-1",
      mentorship_id: "mentorship-1",
      faculty_id: "faculty-1",
      note: "Doing great",
      created_at: null,
      updated_at: null,
    });
    render(<FacultyMentorshipView />);

    await userEvent.click(await screen.findByRole("button", { name: /view mentee/i }));

    expect(await screen.findByText("Jane Student")).toBeInTheDocument();
    expect(screen.getByText(/b\.tech.*cs.*state university/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/private note/i)).toHaveValue("Doing great");
  });

  it("saves the private note", async () => {
    useMentorCapability.mockReturnValue({ status: "ready", canMentor: true });
    listMyMentorships.mockResolvedValue({ mentorships: [mentorship({ status: "ACTIVE" })] });
    getMenteeProfile.mockResolvedValue(bundle());
    getMentorshipNote.mockResolvedValue(null);
    saveMentorshipNote.mockResolvedValue({
      id: "note-1",
      mentorship_id: "mentorship-1",
      faculty_id: "faculty-1",
      note: "Great progress",
      created_at: null,
      updated_at: null,
    });
    render(<FacultyMentorshipView />);

    await userEvent.click(await screen.findByRole("button", { name: /view mentee/i }));
    const noteField = await screen.findByLabelText(/private note/i);
    await userEvent.type(noteField, "Great progress");
    await userEvent.click(screen.getByRole("button", { name: /save note/i }));

    await waitFor(() => expect(saveMentorshipNote).toHaveBeenCalledWith("mentorship-1", "Great progress"));
  });

  it("shows a retryable error state on load failure", async () => {
    useMentorCapability.mockReturnValue({ status: "ready", canMentor: true });
    listMyMentorships
      .mockRejectedValueOnce(new ApiError(500, "Could not load your mentorships."))
      .mockResolvedValueOnce({ mentorships: [] });
    render(<FacultyMentorshipView />);

    expect(await screen.findByText("Could not load your mentorships.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText(/no pending mentorship requests/i)).toBeInTheDocument();
  });
});
