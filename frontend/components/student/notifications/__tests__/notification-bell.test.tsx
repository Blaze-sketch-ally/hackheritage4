import { afterEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ listNotifications: vi.fn() }));

vi.mock("@/lib/student/notifications", () => ({ listNotifications: mocks.listNotifications }));

import { NotificationBell } from "@/components/student/notifications/notification-bell";

describe("NotificationBell", () => {
  afterEach(() => vi.resetAllMocks());

  it("links to the notifications page", () => {
    mocks.listNotifications.mockResolvedValueOnce({ notifications: [], unread_count: 0 });
    const { container } = render(<NotificationBell />);
    expect(container.querySelector('a[href="/student/notifications"]')).not.toBeNull();
  });

  it("shows no badge until a real unread count has loaded", () => {
    mocks.listNotifications.mockReturnValue(new Promise(() => {}));
    const { container } = render(<NotificationBell />);
    expect(container.textContent?.trim()).toBe("");
  });

  it("shows the real unread count once loaded", async () => {
    mocks.listNotifications.mockResolvedValueOnce({ notifications: [], unread_count: 3 });
    const { container } = render(<NotificationBell />);
    await waitFor(() => expect(container.textContent).toContain("3"));
    expect(container.querySelector('a[aria-label="Notifications, 3 unread"]')).not.toBeNull();
  });

  it("shows no badge when there are zero unread", async () => {
    mocks.listNotifications.mockResolvedValueOnce({ notifications: [], unread_count: 0 });
    const { container } = render(<NotificationBell />);
    await waitFor(() => expect(mocks.listNotifications).toHaveBeenCalled());
    expect(container.textContent?.trim()).toBe("");
    expect(container.querySelector('a[aria-label="Notifications"]')).not.toBeNull();
  });

  it("degrades quietly (no badge) if the count request fails", async () => {
    mocks.listNotifications.mockRejectedValueOnce(new Error("boom"));
    const { container } = render(<NotificationBell />);
    await waitFor(() => expect(mocks.listNotifications).toHaveBeenCalled());
    expect(container.textContent?.trim()).toBe("");
  });
});
