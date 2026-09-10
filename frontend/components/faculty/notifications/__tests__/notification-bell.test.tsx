import { afterEach, describe, expect, it, vi } from "vitest";
import { render, waitFor } from "@testing-library/react";

const mocks = vi.hoisted(() => ({ getUnreadCount: vi.fn() }));

vi.mock("@/lib/faculty/notifications", () => ({ getUnreadCount: mocks.getUnreadCount }));

import { NotificationBell } from "@/components/faculty/notifications/notification-bell";

describe("NotificationBell", () => {
  afterEach(() => vi.resetAllMocks());

  it("links to the notifications page", () => {
    mocks.getUnreadCount.mockResolvedValueOnce({ unread_count: 0 });
    const { container } = render(<NotificationBell />);
    expect(container.querySelector('a[href="/faculty/notifications"]')).not.toBeNull();
  });

  it("shows no badge until a real unread count has loaded", () => {
    mocks.getUnreadCount.mockReturnValue(new Promise(() => {}));
    const { container } = render(<NotificationBell />);
    expect(container.textContent?.trim()).toBe("");
  });

  it("shows the real unread count once loaded", async () => {
    mocks.getUnreadCount.mockResolvedValueOnce({ unread_count: 3 });
    const { container } = render(<NotificationBell />);
    await waitFor(() => expect(container.textContent).toContain("3"));
    expect(container.querySelector('a[aria-label="Notifications, 3 unread"]')).not.toBeNull();
  });

  it("shows no badge when there are zero unread", async () => {
    mocks.getUnreadCount.mockResolvedValueOnce({ unread_count: 0 });
    const { container } = render(<NotificationBell />);
    await waitFor(() => expect(mocks.getUnreadCount).toHaveBeenCalled());
    expect(container.textContent?.trim()).toBe("");
    expect(container.querySelector('a[aria-label="Notifications"]')).not.toBeNull();
  });

  it("degrades quietly (no badge) if the count request fails", async () => {
    mocks.getUnreadCount.mockRejectedValueOnce(new Error("boom"));
    const { container } = render(<NotificationBell />);
    await waitFor(() => expect(mocks.getUnreadCount).toHaveBeenCalled());
    expect(container.textContent?.trim()).toBe("");
  });
});
