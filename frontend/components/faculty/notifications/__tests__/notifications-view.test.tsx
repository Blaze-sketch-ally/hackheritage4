import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}));

vi.mock("@/lib/faculty/notifications", () => ({
  listNotifications: mocks.listNotifications,
  markNotificationRead: mocks.markNotificationRead,
  markAllNotificationsRead: mocks.markAllNotificationsRead,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { NotificationsView } from "@/components/faculty/notifications/notifications-view";
import { ApiError } from "@/lib/api";
import type { FacultyNotification } from "@/types/faculty-notification";

function notif(overrides: Partial<FacultyNotification> = {}): FacultyNotification {
  return {
    id: "n-1",
    type: "EVALUATION_ASSIGNED",
    title: "You have been assigned an evaluation",
    body: "A new evaluation is waiting for you in the Evaluation Workspace.",
    related_entity_type: "EVALUATION",
    related_entity_id: "eval-1",
    is_read: false,
    read_at: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("NotificationsView (Faculty)", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.listNotifications.mockReturnValue(new Promise(() => {}));
    render(<NotificationsView />);
    expect(screen.getByLabelText("Loading notifications")).toBeInTheDocument();
  });

  it("renders real notifications with unread styling and count", async () => {
    mocks.listNotifications.mockResolvedValueOnce({
      notifications: [
        notif(),
        notif({ id: "n-2", title: "Your question was approved", is_read: true, type: "REVIEW_DECISION" }),
      ],
      unread_count: 1,
    });
    render(<NotificationsView />);

    expect(await screen.findByText("You have been assigned an evaluation")).toBeInTheDocument();
    expect(screen.getByText("Your question was approved")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /unread \(1\)/i })).toBeInTheDocument();
    expect(screen.getAllByLabelText("Unread")).toHaveLength(1);
  });

  it("shows an honest empty state (no fabricated notifications)", async () => {
    mocks.listNotifications.mockResolvedValueOnce({ notifications: [], unread_count: 0 });
    const { container } = render(<NotificationsView />);
    expect(await screen.findByText("No notifications yet.")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/reconciliation required|new student assigned/i);
  });

  it("shows an error state with retry", async () => {
    mocks.listNotifications.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<NotificationsView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("marks a single notification read", async () => {
    mocks.listNotifications.mockResolvedValueOnce({
      notifications: [notif()],
      unread_count: 1,
    });
    mocks.markNotificationRead.mockResolvedValueOnce(notif({ is_read: true }));
    render(<NotificationsView />);
    await screen.findByText("You have been assigned an evaluation");

    await userEvent.click(screen.getByRole("button", { name: /mark read/i }));

    await waitFor(() => expect(mocks.markNotificationRead).toHaveBeenCalledWith("n-1"));
    await waitFor(() => expect(screen.queryByLabelText("Unread")).not.toBeInTheDocument());
  });

  it("marks all read and re-fetches", async () => {
    mocks.listNotifications
      .mockResolvedValueOnce({
        notifications: [notif(), notif({ id: "n-2", title: "Second update" })],
        unread_count: 2,
      })
      .mockResolvedValueOnce({
        notifications: [
          notif({ is_read: true }),
          notif({ id: "n-2", title: "Second update", is_read: true }),
        ],
        unread_count: 0,
      });
    mocks.markAllNotificationsRead.mockResolvedValueOnce({ updated: 2 });
    render(<NotificationsView />);
    await screen.findByText("Second update");

    await userEvent.click(screen.getByRole("button", { name: /mark all read/i }));

    await waitFor(() => expect(mocks.markAllNotificationsRead).toHaveBeenCalled());
    await waitFor(() =>
      expect(screen.queryByRole("button", { name: /mark all read/i })).not.toBeInTheDocument(),
    );
  });

  it("filters to unread via a server-side request", async () => {
    mocks.listNotifications.mockResolvedValue({ notifications: [notif()], unread_count: 1 });
    render(<NotificationsView />);
    await screen.findByText("You have been assigned an evaluation");
    expect(mocks.listNotifications).toHaveBeenLastCalledWith(undefined);

    await userEvent.click(screen.getByRole("button", { name: /^unread/i }));
    expect(mocks.listNotifications).toHaveBeenLastCalledWith({ unread: true });
  });

  it("links an evaluation-assigned notification to the Evaluation Workspace detail page", async () => {
    mocks.listNotifications.mockResolvedValueOnce({
      notifications: [notif()],
      unread_count: 1,
    });
    const { container } = render(<NotificationsView />);
    await screen.findByText("You have been assigned an evaluation");
    expect(container.querySelector('a[href="/faculty/evaluation-workspace/eval-1"]')).not.toBeNull();
  });

  it("links a review-decision notification to the question detail page", async () => {
    mocks.listNotifications.mockResolvedValueOnce({
      notifications: [
        notif({
          type: "REVIEW_DECISION",
          title: "Your question was approved",
          related_entity_type: "QUESTION",
          related_entity_id: "q-9",
        }),
      ],
      unread_count: 1,
    });
    const { container } = render(<NotificationsView />);
    await screen.findByText("Your question was approved");
    expect(container.querySelector('a[href="/faculty/questions/q-9"]')).not.toBeNull();
  });

  it("links a mentorship notification to the mentorship list page", async () => {
    mocks.listNotifications.mockResolvedValueOnce({
      notifications: [
        notif({
          type: "MENTORSHIP",
          title: "New mentorship request",
          related_entity_type: "MENTORSHIP",
          related_entity_id: "m-1",
        }),
      ],
      unread_count: 1,
    });
    const { container } = render(<NotificationsView />);
    await screen.findByText("New mentorship request");
    expect(container.querySelector('a[href="/faculty/mentorship"]')).not.toBeNull();
  });

  it("renders an evaluation-revoked notification as non-navigable (no related entity)", async () => {
    mocks.listNotifications.mockResolvedValueOnce({
      notifications: [
        notif({
          type: "EVALUATION_REVOKED",
          title: "An evaluation assignment was revoked",
          related_entity_type: null,
          related_entity_id: null,
        }),
      ],
      unread_count: 1,
    });
    const { container } = render(<NotificationsView />);
    await screen.findByText("An evaluation assignment was revoked");
    expect(container.querySelector("a")).toBeNull();
  });
});
