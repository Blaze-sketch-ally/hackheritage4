"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { listNotifications } from "@/lib/industry/notifications";

/**
 * Header entry point to /industry/notifications. Mirrors
 * components/student/notifications/notification-bell.tsx exactly --
 * shows a real unread indicator from GET /api/v1/industry/notifications,
 * never a fabricated dot.
 */
export function NotificationBell() {
  const [unread, setUnread] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    listNotifications({ unread: true, limit: 1 })
      .then(({ unread_count }) => {
        if (!cancelled) setUnread(unread_count);
      })
      .catch(() => {
        if (!cancelled) setUnread(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const hasUnread = unread != null && unread > 0;

  return (
    <Button
      variant="ghost"
      size="icon"
      className="relative"
      aria-label={hasUnread ? `Notifications, ${unread} unread` : "Notifications"}
      render={<Link href="/industry/notifications" />}
      nativeButton={false}
    >
      <Bell />
      {hasUnread && (
        <span
          className="absolute top-1 right-1 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-indigo-500 px-1 text-[10px] font-semibold text-white"
          aria-hidden="true"
        >
          {unread > 9 ? "9+" : unread}
        </span>
      )}
    </Button>
  );
}
