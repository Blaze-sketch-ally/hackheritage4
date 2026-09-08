import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getMyLinkRequests: vi.fn(),
  resolveInstitution: vi.fn(),
  createLinkRequest: vi.fn(),
  cancelLinkRequest: vi.fn(),
}));

vi.mock("@/lib/institution-links", () => ({
  getMyLinkRequests: mocks.getMyLinkRequests,
  resolveInstitution: mocks.resolveInstitution,
  createLinkRequest: mocks.createLinkRequest,
  cancelLinkRequest: mocks.cancelLinkRequest,
}));

import { InstitutionLinkCard } from "@/components/student/institution-link/institution-link-card";
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
    student_name: null,
    student_username: null,
    institution_name: "State College of Engineering",
    ...overrides,
  };
}

describe("InstitutionLinkCard", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state while fetching", () => {
    mocks.getMyLinkRequests.mockReturnValue(new Promise(() => {}));
    render(<InstitutionLinkCard />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows the join form when there is no request yet", async () => {
    mocks.getMyLinkRequests.mockResolvedValueOnce({ requests: [] });
    render(<InstitutionLinkCard />);
    expect(await screen.findByLabelText("Institution username")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Send Request" })).toBeInTheDocument();
  });

  it("shows a pending state with a cancel action", async () => {
    mocks.getMyLinkRequests.mockResolvedValueOnce({ requests: [linkRequest()] });
    render(<InstitutionLinkCard />);
    expect(
      await screen.findByText(/Request sent to State College of Engineering/i),
    ).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
  });

  it("shows a linked (approved) state with no join form", async () => {
    mocks.getMyLinkRequests.mockResolvedValueOnce({
      requests: [linkRequest({ status: "APPROVED" })],
    });
    render(<InstitutionLinkCard />);
    expect(await screen.findByText(/Linked to State College of Engineering/i)).toBeInTheDocument();
    expect(screen.queryByLabelText("Institution username")).not.toBeInTheDocument();
  });

  it("shows the join form again after a rejected request, with context", async () => {
    mocks.getMyLinkRequests.mockResolvedValueOnce({
      requests: [linkRequest({ status: "REJECTED" })],
    });
    render(<InstitutionLinkCard />);
    expect(
      await screen.findByText(/request to join State College of Engineering was rejected/i),
    ).toBeInTheDocument();
    expect(screen.getByLabelText("Institution username")).toBeInTheDocument();
  });

  it("resolves the institution then creates a request on submit", async () => {
    mocks.getMyLinkRequests.mockResolvedValueOnce({ requests: [] });
    mocks.resolveInstitution.mockResolvedValueOnce({ id: "institution-1", full_name: "State College" });
    mocks.createLinkRequest.mockResolvedValueOnce(linkRequest());

    render(<InstitutionLinkCard />);
    const input = await screen.findByLabelText("Institution username");
    await userEvent.type(input, "state_college");
    await userEvent.click(screen.getByRole("button", { name: "Send Request" }));

    await waitFor(() => expect(mocks.resolveInstitution).toHaveBeenCalledWith("state_college"));
    expect(mocks.createLinkRequest).toHaveBeenCalledWith("institution-1");
    expect(await screen.findByText(/Request sent to State College of Engineering/i)).toBeInTheDocument();
  });

  it("shows a not-found message when the institution username does not resolve", async () => {
    mocks.getMyLinkRequests.mockResolvedValueOnce({ requests: [] });
    mocks.resolveInstitution.mockRejectedValueOnce(new ApiError(404, "not found"));

    render(<InstitutionLinkCard />);
    const input = await screen.findByLabelText("Institution username");
    await userEvent.type(input, "nope");
    await userEvent.click(screen.getByRole("button", { name: "Send Request" }));

    expect(
      await screen.findByText("No institution account found with that username."),
    ).toBeInTheDocument();
    expect(mocks.createLinkRequest).not.toHaveBeenCalled();
  });

  it("surfaces an already-linked error from the API", async () => {
    mocks.getMyLinkRequests.mockResolvedValueOnce({ requests: [] });
    mocks.resolveInstitution.mockResolvedValueOnce({ id: "institution-1", full_name: "State College" });
    mocks.createLinkRequest.mockRejectedValueOnce(new ApiError(409, "You already have a pending institution link."));

    render(<InstitutionLinkCard />);
    const input = await screen.findByLabelText("Institution username");
    await userEvent.type(input, "state_college");
    await userEvent.click(screen.getByRole("button", { name: "Send Request" }));

    expect(
      await screen.findByText("You already have a pending institution link."),
    ).toBeInTheDocument();
  });

  it("cancels a pending request", async () => {
    mocks.getMyLinkRequests.mockResolvedValueOnce({ requests: [linkRequest()] });
    mocks.cancelLinkRequest.mockResolvedValueOnce(linkRequest({ status: "CANCELLED" }));

    render(<InstitutionLinkCard />);
    await userEvent.click(await screen.findByRole("button", { name: "Cancel" }));

    await waitFor(() => expect(mocks.cancelLinkRequest).toHaveBeenCalledWith("req-1"));
    expect(await screen.findByLabelText("Institution username")).toBeInTheDocument();
  });
});
