"use client";

import Link from "next/link";
import {
  Bell,
  BookOpen,
  Briefcase,
  CalendarDays,
  CheckCircle2,
  ClipboardCheck,
  Info,
  Users,
} from "lucide-react";
import type { LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { relatedHref } from "@/types/student-notification";
import type { NotificationType, StudentNotification } from "@/types/student-notification";

const TYPE_ICON: Record<NotificationType, LucideIcon> = {
  APPLICATION_STATUS: Briefcase,
  INTERVIEW: Users,
  ASSESSMENT: ClipboardCheck,
  LEARNING: BookOpen,
  MENTORSHIP: Users,
  EVENT: CalendarDays,
  SYSTEM: Info,
  INTERNSHIP: Briefcase,
};

function relativeTime(iso: string | null): string {
  if (!iso) return "";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "";
  const diff = Date.now() - then;
  const min = Math.round(diff / 60000);
  if (min < 1) return "just now";
  if (min < 60) return `${min}m ago`;
  const hr = Math.round(min / 60);
  if (hr < 24) return `${hr}h ago`;
  const day = Math.round(hr / 24);
  if (day < 7) return `${day}d ago`;
  return new Date(iso).toLocaleDateString();
}

export function NotificationItem({
  notification,
  onMarkRead,
  busy,
}: {
  notification: StudentNotification;
  onMarkRead: (id: string) => void;
  busy: boolean;
}) {
  const Icon = TYPE_ICON[notification.type] ?? Bell;
  const href = relatedHref(notification);

  const body = (
    <div className="flex gap-3">
      <span
        className={cn(
          "mt-0.5 flex size-8 shrink-0 items-center justify-center rounded-full",
          notification.is_read ? "bg-muted text-muted-foreground" : "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
        )}
      >
        <Icon className="size-4" aria-hidden="true" />
      </span>
      <div className="min-w-0 flex-1">
        <div className="flex items-start gap-2">
          <p className={cn("text-sm", !notification.is_read && "font-semibold")}>
            {notification.title}
          </p>
          {!notification.is_read && (
            <span
              className="mt-1.5 size-2 shrink-0 rounded-full bg-indigo-500"
              aria-label="Unread"
            />
          )}
        </div>
        <p className="text-sm whitespace-pre-wrap text-muted-foreground">{notification.body}</p>
        <p className="mt-1 text-xs text-muted-foreground">{relativeTime(notification.created_at)}</p>
      </div>
    </div>
  );

  return (
    <div
      className={cn(
        "rounded-lg border px-3 py-3 transition-colors",
        notification.is_read ? "bg-card" : "border-indigo-500/20 bg-indigo-500/[0.03]",
      )}
    >
      {href ? (
        <Link
          href={href}
          className="block rounded-md focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50"
          onClick={() => {
            if (!notification.is_read) onMarkRead(notification.id);
          }}
        >
          {body}
        </Link>
      ) : (
        body
      )}

      {!notification.is_read && (
        <div className="mt-2 flex justify-end">
          <Button
            variant="ghost"
            size="sm"
            className="h-7 gap-1 text-xs text-muted-foreground"
            disabled={busy}
            onClick={() => onMarkRead(notification.id)}
          >
            <CheckCircle2 className="size-3.5" /> Mark read
          </Button>
        </div>
      )}
    </div>
  );
}
