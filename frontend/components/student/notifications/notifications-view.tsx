"use client";

import { useEffect, useState } from "react";
import { BellOff, CheckCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorState } from "@/components/common/error-state";
import { NotificationItem } from "@/components/student/notifications/notification-item";
import { ApiError } from "@/lib/api";
import {
  listNotifications,
  markAllNotificationsRead,
  markNotificationRead,
} from "@/lib/student/notifications";
import type { StudentNotification } from "@/types/student-notification";

type Filter = "all" | "unread";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; notifications: StudentNotification[]; unreadCount: number };

export function NotificationsView() {
  const [filter, setFilter] = useState<Filter>("all");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [bulkBusy, setBulkBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    listNotifications(filter === "unread" ? { unread: true } : undefined)
      .then(({ notifications, unread_count }) => {
        if (!cancelled)
          setState({ status: "ready", notifications, unreadCount: unread_count });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: err instanceof ApiError ? err.message : "Could not load your notifications.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [filter, reloadKey]);

  async function handleMarkRead(id: string) {
    setBusyId(id);
    try {
      await markNotificationRead(id);
      setState((s) => {
        if (s.status !== "ready") return s;
        const notifications =
          filter === "unread"
            ? s.notifications.filter((n) => n.id !== id)
            : s.notifications.map((n) => (n.id === id ? { ...n, is_read: true } : n));
        return {
          ...s,
          notifications,
          unreadCount: Math.max(0, s.unreadCount - 1),
        };
      });
    } catch {
      // A failed mark-read shouldn't blow away the list; a reload will resync.
      setReloadKey((k) => k + 1);
    } finally {
      setBusyId(null);
    }
  }

  async function handleMarkAll() {
    setBulkBusy(true);
    try {
      await markAllNotificationsRead();
      setReloadKey((k) => k + 1);
    } catch {
      setReloadKey((k) => k + 1);
    } finally {
      setBulkBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1.5">
          <Button
            variant={filter === "all" ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter("all")}
          >
            All
          </Button>
          <Button
            variant={filter === "unread" ? "default" : "outline"}
            size="sm"
            onClick={() => setFilter("unread")}
          >
            Unread
            {state.status === "ready" && state.unreadCount > 0 ? ` (${state.unreadCount})` : ""}
          </Button>
        </div>
        {state.status === "ready" && state.unreadCount > 0 && (
          <Button variant="ghost" size="sm" onClick={handleMarkAll} disabled={bulkBusy}>
            <CheckCheck className="size-4" /> Mark all read
          </Button>
        )}
      </div>

      {state.status === "loading" && <NotificationsSkeleton />}

      {state.status === "error" && (
        <ErrorState
          message={state.message}
          onRetry={() => {
            setState({ status: "loading" });
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {state.status === "ready" && state.notifications.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
            <BellOff className="size-8" aria-hidden="true" />
            <p className="font-medium text-foreground">
              {filter === "unread" ? "You're all caught up." : "No notifications yet."}
            </p>
            <p className="text-sm">
              Updates about your applications, assessments, and more will show up here.
            </p>
          </CardContent>
        </Card>
      )}

      {state.status === "ready" && state.notifications.length > 0 && (
        <div className="flex flex-col gap-2">
          {state.notifications.map((notification) => (
            <NotificationItem
              key={notification.id}
              notification={notification}
              onMarkRead={handleMarkRead}
              busy={busyId === notification.id}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function NotificationsSkeleton() {
  return (
    <div className="flex flex-col gap-2" aria-busy="true" aria-label="Loading notifications">
      {[0, 1, 2, 3].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="flex gap-3 py-4">
            <div className="size-8 shrink-0 rounded-full bg-muted" />
            <div className="flex-1 space-y-2">
              <div className="h-3 w-1/3 rounded bg-muted" />
              <div className="h-3 w-2/3 rounded bg-muted" />
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
