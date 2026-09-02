import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listNotifications: vi.fn(),
  markNotificationRead: vi.fn(),
  markAllNotificationsRead: vi.fn(),
}));

vi.mock("@/lib/student/notifications", () => ({
  listNotifications: mocks.listNotifications,
  markNotificationRead: mocks.markNotificationRead,
  markAllNotificationsRead: mocks.markAllNotificationsRead,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: vi.fn() }) }));

import { NotificationsView } from "@/components/student/notifications/notifications-view";
import { ApiError } from "@/lib/api";
import type { StudentNotification } from "@/types/student-notification";

function notif(overrides: Partial<StudentNotification> = {}): StudentNotification {
  return {
    id: "n-1",
    type: "APPLICATION_STATUS",
    title: "Application update",
    body: "Your application moved to Under Review.",
    related_entity_type: "APPLICATION",
    related_entity_id: "app-1",
    is_read: false,
    read_at: null,
    created_at: new Date().toISOString(),
    ...overrides,
  };
}

describe("NotificationsView", () => {
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
        notif({ id: "n-2", title: "Assessment ready", is_read: true, type: "ASSESSMENT" }),
      ],
      unread_count: 1,
    });
    render(<NotificationsView />);

    expect(await screen.findByText("Application update")).toBeInTheDocument();
    expect(screen.getByText("Assessment ready")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /unread \(1\)/i })).toBeInTheDocument();
    // one unread marker for the single unread row
    expect(screen.getAllByLabelText("Unread")).toHaveLength(1);
  });

  it("shows an honest empty state (no fabricated notifications)", async () => {
    mocks.listNotifications.mockResolvedValueOnce({ notifications: [], unread_count: 0 });
    const { container } = render(<NotificationsView />);
    expect(await screen.findByText("No notifications yet.")).toBeInTheDocument();
    expect(container.textContent).not.toMatch(/shortlisted|new mentor available|assessment completed/i);
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
    await screen.findByText("Application update");

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
    await screen.findByText("Application update");
    expect(mocks.listNotifications).toHaveBeenLastCalledWith(undefined);

    await userEvent.click(screen.getByRole("button", { name: /^unread/i }));
    expect(mocks.listNotifications).toHaveBeenLastCalledWith({ unread: true });
  });

  it("links a notification with a known related entity to a real student route", async () => {
    mocks.listNotifications.mockResolvedValueOnce({
      notifications: [
        notif({ type: "EVENT", related_entity_type: "EVENT", related_entity_id: "ev-9" }),
      ],
      unread_count: 1,
    });
    const { container } = render(<NotificationsView />);
    await screen.findByText("Application update");
    expect(container.querySelector('a[href="/student/events/ev-9"]')).not.toBeNull();
  });

  it("renders an interview notification as non-navigable (no student route exists)", async () => {
    mocks.listNotifications.mockResolvedValueOnce({
      notifications: [
        notif({ type: "INTERVIEW", related_entity_type: "INTERVIEW", related_entity_id: "iv-1" }),
      ],
      unread_count: 1,
    });
    const { container } = render(<NotificationsView />);
    await screen.findByText("Application update");
    expect(container.querySelector("a")).toBeNull();
  });
});
