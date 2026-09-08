import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getIncomingLinkRequests: vi.fn(),
  approveLinkRequest: vi.fn(),
  rejectLinkRequest: vi.fn(),
  getInstitutionStudents: vi.fn(),
}));

vi.mock("@/lib/institution-links", () => ({
  getIncomingLinkRequests: mocks.getIncomingLinkRequests,
  approveLinkRequest: mocks.approveLinkRequest,
  rejectLinkRequest: mocks.rejectLinkRequest,
  unlinkStudent: vi.fn(),
}));

// The Student Directory (a child of this view) fetches independently --
// stubbed here so these tests exercise only the Pending Requests section;
// the directory itself has its own dedicated test file.
vi.mock("@/lib/institution/students", () => ({
  getInstitutionStudents: mocks.getInstitutionStudents,
}));

vi.mock("next/navigation", () => ({
  useRouter: () => ({ push: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}));

import { InstitutionStudentsView } from "@/components/institution/students/institution-students-view";
import { ApiError } from "@/lib/api";
import type { InstitutionLinkRequest } from "@/types/institution-link";

function linkRequest(overrides: Partial<InstitutionLinkRequest> = {}): InstitutionLinkRequest {
  return {
    id: "req-1",
    student_id: "student-1",
    institution_id: "institution-1",
    status: "PENDING",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    student_name: "Priya Sharma",
    student_username: "priya_s",
    institution_name: null,
    ...overrides,
  };
}

const EMPTY_DIRECTORY = {
  students: [],
  total: 0,
  page: 1,
  page_size: 20,
  filters: { departments: [], batches: [] },
  summary: { total_students: 0, placed: 0, unplaced: 0, no_applications: 0, internship_selected: 0 },
};

describe("InstitutionStudentsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("does not fetch more than once on mount", () => {
    mocks.getIncomingLinkRequests.mockReturnValue(new Promise(() => {}));
    mocks.getInstitutionStudents.mockResolvedValue(EMPTY_DIRECTORY);
    render(<InstitutionStudentsView />);
    expect(mocks.getIncomingLinkRequests).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getIncomingLinkRequests.mockReturnValue(new Promise(() => {}));
    mocks.getInstitutionStudents.mockResolvedValue(EMPTY_DIRECTORY);
    render(<InstitutionStudentsView />);
    expect(screen.getByText(/Loading your students/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getIncomingLinkRequests.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    mocks.getInstitutionStudents.mockResolvedValue(EMPTY_DIRECTORY);
    render(<InstitutionStudentsView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no pending requests", async () => {
    mocks.getIncomingLinkRequests.mockResolvedValueOnce({ requests: [] });
    mocks.getInstitutionStudents.mockResolvedValue(EMPTY_DIRECTORY);
    render(<InstitutionStudentsView />);
    expect(await screen.findByText("No pending requests")).toBeInTheDocument();
  });

  it("lists a pending request with approve/reject actions", async () => {
    mocks.getIncomingLinkRequests.mockResolvedValueOnce({ requests: [linkRequest()] });
    mocks.getInstitutionStudents.mockResolvedValue(EMPTY_DIRECTORY);
    render(<InstitutionStudentsView />);

    expect(await screen.findByText("Priya Sharma")).toBeInTheDocument();
    expect(screen.getByText("@priya_s")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Approve" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Reject" })).toBeInTheDocument();
  });

  it("only shows PENDING requests in this section, not approved ones", async () => {
    mocks.getIncomingLinkRequests.mockResolvedValueOnce({
      requests: [linkRequest({ id: "req-2", status: "APPROVED", student_name: "Rahul Verma" })],
    });
    mocks.getInstitutionStudents.mockResolvedValue(EMPTY_DIRECTORY);
    render(<InstitutionStudentsView />);

    expect(await screen.findByText("No pending requests")).toBeInTheDocument();
    expect(screen.queryByText("Rahul Verma")).not.toBeInTheDocument();
  });

  it("renders the Student Directory below the pending requests", async () => {
    mocks.getIncomingLinkRequests.mockResolvedValueOnce({ requests: [] });
    mocks.getInstitutionStudents.mockResolvedValue(EMPTY_DIRECTORY);
    render(<InstitutionStudentsView />);
    await screen.findByText("No pending requests");
    expect(await screen.findByText("Total Students")).toBeInTheDocument();
  });

  it("approves a request through the confirmation dialog", async () => {
    mocks.getIncomingLinkRequests.mockResolvedValueOnce({ requests: [linkRequest()] });
    mocks.approveLinkRequest.mockResolvedValueOnce(linkRequest({ status: "APPROVED" }));
    mocks.getInstitutionStudents.mockResolvedValue(EMPTY_DIRECTORY);

    render(<InstitutionStudentsView />);
    await screen.findByText("Priya Sharma");

    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Approve" }));

    await waitFor(() => expect(mocks.approveLinkRequest).toHaveBeenCalledWith("req-1"));
    expect(await screen.findByText("Student approved.")).toBeInTheDocument();
  });

  it("rejects a request through the destructive confirmation dialog", async () => {
    mocks.getIncomingLinkRequests.mockResolvedValueOnce({ requests: [linkRequest()] });
    mocks.rejectLinkRequest.mockResolvedValueOnce(linkRequest({ status: "REJECTED" }));
    mocks.getInstitutionStudents.mockResolvedValue(EMPTY_DIRECTORY);

    render(<InstitutionStudentsView />);
    await screen.findByText("Priya Sharma");

    await userEvent.click(screen.getByRole("button", { name: "Reject" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Reject" }));

    await waitFor(() => expect(mocks.rejectLinkRequest).toHaveBeenCalledWith("req-1"));
    expect(await screen.findByText("Request rejected.")).toBeInTheDocument();
  });

  it("does not call approve until the confirmation dialog is confirmed", async () => {
    mocks.getIncomingLinkRequests.mockResolvedValueOnce({ requests: [linkRequest()] });
    mocks.getInstitutionStudents.mockResolvedValue(EMPTY_DIRECTORY);
    render(<InstitutionStudentsView />);
    await screen.findByText("Priya Sharma");

    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    await screen.findByRole("dialog");

    expect(mocks.approveLinkRequest).not.toHaveBeenCalled();
  });

  it("surfaces an approve error from the API", async () => {
    mocks.getIncomingLinkRequests.mockResolvedValueOnce({ requests: [linkRequest()] });
    mocks.approveLinkRequest.mockRejectedValueOnce(
      new ApiError(409, "Only a pending request can be approved."),
    );
    mocks.getInstitutionStudents.mockResolvedValue(EMPTY_DIRECTORY);

    render(<InstitutionStudentsView />);
    await screen.findByText("Priya Sharma");
    await userEvent.click(screen.getByRole("button", { name: "Approve" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Approve" }));

    expect(await screen.findByText("Only a pending request can be approved.")).toBeInTheDocument();
  });
});
