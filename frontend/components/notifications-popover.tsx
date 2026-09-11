"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowRight,
  Award,
  Bell,
  BellOff,
  Briefcase,
  Calendar,
  CheckCheck,
  CheckCircle2,
  GraduationCap,
  HelpCircle,
  Loader2,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Popover,
  PopoverContent,
  PopoverTrigger,
} from "@/components/ui/popover";
import { toast } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";
import {
  listNotifications as listStudentNotifications,
  markAllNotificationsRead as markAllStudentRead,
  markNotificationRead as markStudentRead,
} from "@/lib/student/notifications";
import {
  listNotifications as listFacultyNotifications,
  markAllNotificationsRead as markAllFacultyRead,
  markNotificationRead as markFacultyRead,
} from "@/lib/faculty/notifications";
import {
  relatedHref as studentRelatedHref,
  type StudentNotification,
} from "@/types/student-notification";
import {
  relatedHref as facultyRelatedHref,
  type FacultyNotification,
} from "@/types/faculty-notification";
import type { PublicRole } from "@/lib/constants";

type GenericNotification = {
  id: string;
  title: string;
  body: string;
  type: string;
  is_read: boolean;
  created_at: string | null;
  href?: string | null;
};

function formatTimeAgo(dateString: string | null): string {
  if (!dateString) return "";
  const now = new Date();
  const date = new Date(dateString);
  const seconds = Math.floor((now.getTime() - date.getTime()) / 1000);
  if (isNaN(seconds) || seconds < 0) return "";

  if (seconds < 60) return "just now";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  const days = Math.floor(hours / 24);
  if (days < 7) return `${days}d ago`;

  return date.toLocaleDateString(undefined, {
    month: "short",
    day: "numeric",
  });
}

function getNotificationIcon(type: string, role?: string | null) {
  if (role === "FACULTY") {
    switch (type) {
      case "QUESTION":
        return HelpCircle;
      case "EVALUATION_ASSIGNED":
      case "EVALUATION_REVOKED":
      case "REVIEW_DECISION":
        return Award;
      case "MENTORSHIP":
        return Users;
      default:
        return Bell;
    }
  }

  switch (type) {
    case "APPLICATION_STATUS":
    case "INTERNSHIP":
      return Briefcase;
    case "INTERVIEW":
    case "EVENT":
      return Calendar;
    case "ASSESSMENT":
      return CheckCircle2;
    case "LEARNING":
    case "JOB_TRAINING":
      return GraduationCap;
    case "MENTORSHIP":
      return Users;
    default:
      return Bell;
  }
}

export interface NotificationsPopoverProps {
  role?: PublicRole | "ADMIN" | null;
  className?: string;
}

export function NotificationsPopover({
  role = "STUDENT",
  className,
}: NotificationsPopoverProps) {
  const [open, setOpen] = React.useState(false);
  const [loading, setLoading] = React.useState(false);
  const [unreadCount, setUnreadCount] = React.useState<number>(0);
  const [notifications, setNotifications] = React.useState<GenericNotification[]>([]);
  const [markingAll, setMarkingAll] = React.useState(false);

  const isStudent = role === "STUDENT";
  const isFaculty = role === "FACULTY";
  const hasLiveNotifications = isStudent || isFaculty;

  // Load preview items (latest 5). Called directly from the popover's
  // onOpenChange handler (a real user event), not from an effect --
  // this is an event-triggered fetch, not a mount-time sync.
  const fetchRecent = React.useCallback(async () => {
    setLoading(true);
    try {
      if (isStudent) {
        const res = await listStudentNotifications({ limit: 5 });
        setUnreadCount(res.unread_count ?? 0);
        const mapped: GenericNotification[] = res.notifications.map((n: StudentNotification) => ({
          id: n.id,
          title: n.title,
          body: n.body,
          type: n.type,
          is_read: n.is_read,
          created_at: n.created_at,
          href: studentRelatedHref(n),
        }));
        setNotifications(mapped);
      } else if (isFaculty) {
        const res = await listFacultyNotifications({ limit: 5 });
        setUnreadCount(res.unread_count ?? 0);
        const mapped: GenericNotification[] = res.notifications.map((n: FacultyNotification) => ({
          id: n.id,
          title: n.title,
          body: n.body,
          type: n.type,
          is_read: n.is_read,
          created_at: n.created_at,
          href: facultyRelatedHref(n),
        }));
        setNotifications(mapped);
      }
    } catch {
      setNotifications([]);
    } finally {
      setLoading(false);
    }
  }, [isStudent, isFaculty]);

  // Load unread count on mount.
  React.useEffect(() => {
    if (!hasLiveNotifications) return;
    let cancelled = false;

    async function fetchCount() {
      try {
        if (isStudent) {
          const res = await listStudentNotifications({ unread: true, limit: 1 });
          if (!cancelled) setUnreadCount(res.unread_count ?? 0);
        } else if (isFaculty) {
          const res = await listFacultyNotifications({ unread: true, limit: 1 });
          if (!cancelled) setUnreadCount(res.unread_count ?? 0);
        }
      } catch {
        // Quiet fail for header badges
        if (!cancelled) setUnreadCount(0);
      }
    }

    void fetchCount();
    return () => {
      cancelled = true;
    };
  }, [hasLiveNotifications, isStudent, isFaculty]);

  function handleOpenChange(next: boolean) {
    setOpen(next);
    if (next && hasLiveNotifications) {
      fetchRecent();
    }
  }

  async function handleMarkAllRead() {
    if (markingAll) return;
    setMarkingAll(true);
    try {
      if (isStudent) {
        await markAllStudentRead();
      } else if (isFaculty) {
        await markAllFacultyRead();
      }
      setUnreadCount(0);
      setNotifications((prev) =>
        prev.map((item) => ({ ...item, is_read: true }))
      );
      toast.success("All notifications marked as read");
    } catch {
      toast.error("Failed to mark all notifications as read");
      // Ignore
    } finally {
      setMarkingAll(false);
    }
  }

  async function handleItemClick(item: GenericNotification) {
    if (!item.is_read) {
      try {
        if (isStudent) {
          await markStudentRead(item.id);
        } else if (isFaculty) {
          await markFacultyRead(item.id);
        }
        setNotifications((prev) =>
          prev.map((n) => (n.id === item.id ? { ...n, is_read: true } : n))
        );
        setUnreadCount((prev) => Math.max(0, prev - 1));
      } catch {
        // Ignore
      }
    }
    setOpen(false);
  }

  const hasUnread = unreadCount > 0;

  const viewAllHref = isStudent
    ? "/student/notifications"
    : isFaculty
    ? "/faculty/notifications"
    : role === "INDUSTRY"
    ? "/industry/dashboard"
    : "/institution/dashboard";

  const emptyStateText = (() => {
    if (isStudent) {
      return {
        title: "You're all caught up",
        description: "Application updates, interview invites, and test results will appear here.",
      };
    }
    if (isFaculty) {
      return {
        title: "You're all caught up",
        description: "Assigned evaluations, question approvals, and mentorship alerts will appear here.",
      };
    }
    if (role === "INDUSTRY") {
      return {
        title: "No new notifications",
        description: "Candidate applications, candidate shortlist status, and interview notices will appear here.",
      };
    }
    if (role === "INSTITUTION") {
      return {
        title: "No new notifications",
        description: "Institutional placement drives, student milestones, and departmental metrics will appear here.",
      };
    }
    return {
      title: "No notifications",
      description: "You have no unread notifications at this time.",
    };
  })();

  return (
    <Popover open={open} onOpenChange={handleOpenChange}>
      <PopoverTrigger
        render={
          <Button
            variant="ghost"
            size="icon"
            className={cn("relative text-foreground/80 hover:text-foreground", className)}
            aria-label={hasUnread ? `Notifications, ${unreadCount} unread` : "Notifications"}
          />
        }
      >
        <Bell className="size-4" />
        {hasUnread && (
          <span
            className="absolute top-1.5 right-1.5 flex min-h-4 min-w-4 items-center justify-center rounded-full bg-primary px-1 text-[10px] font-semibold text-primary-foreground shadow-xs"
            aria-hidden="true"
          >
            {unreadCount > 9 ? "9+" : unreadCount}
          </span>
        )}
      </PopoverTrigger>

      <PopoverContent align="end" side="bottom" sideOffset={6} className="w-80 sm:w-96">
        {/* Header */}
        <div className="flex items-center justify-between border-b border-border/60 px-4 py-3">
          <div className="flex items-center gap-2">
            <span className="text-sm font-semibold tracking-tight">Notifications</span>
            {hasUnread && (
              <span className="rounded-full bg-primary/10 px-2 py-0.5 text-xs font-medium text-primary">
                {unreadCount} new
              </span>
            )}
          </div>
          {hasUnread && (
            <button
              type="button"
              onClick={handleMarkAllRead}
              disabled={markingAll}
              className="flex items-center gap-1 text-xs text-muted-foreground transition hover:text-foreground disabled:opacity-50"
            >
              {markingAll ? (
                <Loader2 className="size-3 animate-spin" />
              ) : (
                <CheckCheck className="size-3.5" />
              )}
              <span>Mark all read</span>
            </button>
          )}
        </div>

        {/* Content */}
        {loading ? (
          <div className="flex flex-col items-center justify-center gap-2 py-10 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
            <span className="text-xs">Loading alerts...</span>
          </div>
        ) : !hasLiveNotifications || notifications.length === 0 ? (
          <div className="flex flex-col items-center justify-center gap-2 px-6 py-8 text-center">
            <div className="flex size-10 items-center justify-center rounded-full bg-muted/60 text-muted-foreground">
              <BellOff className="size-5" />
            </div>
            <p className="text-sm font-medium text-foreground">{emptyStateText.title}</p>
            <p className="text-xs text-muted-foreground leading-relaxed">
              {emptyStateText.description}
            </p>
          </div>
        ) : (
          <div className="max-h-[320px] overflow-y-auto divide-y divide-border/40">
            {notifications.map((item) => {
              const Icon = getNotificationIcon(item.type, role);
              const content = (
                <div
                  className={cn(
                    "group flex items-start gap-3 p-3.5 transition hover:bg-muted/40 text-left",
                    !item.is_read && "bg-primary/[0.03]"
                  )}
                >
                  <div
                    className={cn(
                      "flex size-8 shrink-0 items-center justify-center rounded-lg text-xs",
                      item.is_read
                        ? "bg-muted text-muted-foreground"
                        : "bg-primary/10 text-primary"
                    )}
                  >
                    <Icon className="size-4" />
                  </div>

                  <div className="min-w-0 flex-1 space-y-1">
                    <div className="flex items-center justify-between gap-1.5">
                      <p
                        className={cn(
                          "text-xs leading-snug line-clamp-1",
                          item.is_read
                            ? "font-normal text-muted-foreground"
                            : "font-medium text-foreground"
                        )}
                      >
                        {item.title}
                      </p>
                      {item.created_at && (
                        <span className="shrink-0 text-[10px] text-muted-foreground/80">
                          {formatTimeAgo(item.created_at)}
                        </span>
                      )}
                    </div>
                    <p className="text-xs text-muted-foreground line-clamp-2 leading-relaxed">
                      {item.body}
                    </p>
                  </div>

                  {!item.is_read && (
                    <span
                      className="mt-1.5 size-2 shrink-0 rounded-full bg-primary"
                      aria-label="Unread"
                    />
                  )}
                </div>
              );

              if (item.href) {
                return (
                  <Link
                    key={item.id}
                    href={item.href}
                    onClick={() => handleItemClick(item)}
                    className="block focus-visible:outline-none focus-visible:bg-muted/50"
                  >
                    {content}
                  </Link>
                );
              }

              return (
                <button
                  key={item.id}
                  type="button"
                  onClick={() => handleItemClick(item)}
                  className="w-full text-left focus-visible:outline-none focus-visible:bg-muted/50"
                >
                  {content}
                </button>
              );
            })}
          </div>
        )}

        {/* Footer */}
        {hasLiveNotifications && (
          <div className="border-t border-border/60 p-2.5 text-center">
            <Link
              href={viewAllHref}
              onClick={() => setOpen(false)}
              className="inline-flex items-center justify-center gap-1.5 text-xs font-medium text-primary hover:text-primary/80 transition"
            >
              <span>View all notifications</span>
              <ArrowRight className="size-3" />
            </Link>
          </div>
        )}
      </PopoverContent>
    </Popover>
  );
}
