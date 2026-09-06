"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Bell } from "lucide-react";
import { Button } from "@/components/ui/button";
import { listNotifications } from "@/lib/student/notifications";

/**
 * Header entry point to /student/notifications. Shows a real unread
 * indicator from GET /api/v1/student/notifications (the `unread_count`
 * field) — no badge is shown until the count is actually loaded and > 0,
 * so there is never a fabricated "you have notifications" dot.
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
        // A failed count must never block the header — just show no badge.
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
      render={<Link href="/student/notifications" />}
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
