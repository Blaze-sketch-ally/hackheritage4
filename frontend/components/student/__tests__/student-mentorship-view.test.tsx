import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listMyMentorships, requestMentorship, updateMentorshipStatus } = vi.hoisted(() => ({
  listMyMentorships: vi.fn(),
  requestMentorship: vi.fn(),
  updateMentorshipStatus: vi.fn(),
}));

vi.mock("@/lib/student/mentorships", () => ({
  listMyMentorships,
  requestMentorship,
  updateMentorshipStatus,
}));

import { StudentMentorshipView } from "@/components/student/student-mentorship-view";
import { ApiError } from "@/lib/api";

function mentorship(overrides = {}) {
  return {
    id: "mentorship-1",
    faculty_id: "faculty-1",
    student_id: "student-1",
    requested_by: "student-1",
    status: "REQUESTED",
    focus_area: "Career guidance",
    start_date: null,
    end_date: null,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("StudentMentorshipView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("requests a mentor by faculty id", async () => {
    listMyMentorships.mockResolvedValue({ mentorships: [] });
    requestMentorship.mockResolvedValue(mentorship());
    render(<StudentMentorshipView />);

    await waitFor(() => expect(listMyMentorships).toHaveBeenCalled());
    await userEvent.type(screen.getByLabelText("Faculty ID"), "faculty-1");
    await userEvent.click(screen.getByRole("button", { name: /request mentorship/i }));

    await waitFor(() => expect(requestMentorship).toHaveBeenCalledWith("faculty-1", null));
  });

  it("shows Withdraw for a request the student made", async () => {
    listMyMentorships.mockResolvedValue({ mentorships: [mentorship({ requested_by: "student-1" })] });
    updateMentorshipStatus.mockResolvedValue(mentorship({ status: "WITHDRAWN" }));
    render(<StudentMentorshipView />);

    expect(await screen.findByRole("button", { name: "Withdraw" })).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: "Withdraw" }));
    await waitFor(() => expect(updateMentorshipStatus).toHaveBeenCalledWith("mentorship-1", "WITHDRAWN"));
  });

  it("shows Accept/Decline for a request the faculty member made", async () => {
    listMyMentorships.mockResolvedValue({ mentorships: [mentorship({ requested_by: "faculty-1" })] });
    updateMentorshipStatus.mockResolvedValue(mentorship({ status: "ACCEPTED" }));
    render(<StudentMentorshipView />);

    expect(await screen.findByRole("button", { name: "Accept" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Decline" })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Accept" }));
    await waitFor(() => expect(updateMentorshipStatus).toHaveBeenCalledWith("mentorship-1", "ACCEPTED"));
  });

  it("shows Complete/End for an ACTIVE mentorship and no mentee-details action", async () => {
    listMyMentorships.mockResolvedValue({ mentorships: [mentorship({ status: "ACTIVE" })] });
    render(<StudentMentorshipView />);

    expect(await screen.findByRole("button", { name: "Complete" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "End" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /view/i })).not.toBeInTheDocument();
  });

  it("shows an honest empty state when there are none", async () => {
    listMyMentorships.mockResolvedValue({ mentorships: [] });
    render(<StudentMentorshipView />);
    expect(await screen.findByText(/don't have any mentorships/i)).toBeInTheDocument();
  });

  it("shows a retryable error state on load failure", async () => {
    listMyMentorships
      .mockRejectedValueOnce(new ApiError(500, "Could not load your mentorships."))
      .mockResolvedValueOnce({ mentorships: [] });
    render(<StudentMentorshipView />);

    expect(await screen.findByText("Could not load your mentorships.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText(/don't have any mentorships/i)).toBeInTheDocument();
  });
});
