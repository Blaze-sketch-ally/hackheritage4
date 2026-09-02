"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowRight, CalendarDays } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { listEvents } from "@/lib/student/events";
import { STUDENT_EVENT_WORK_MODE_LABELS } from "@/types/student-event";
import type { StudentEventSummary } from "@/types/student-event";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; events: StudentEventSummary[] };

const PREVIEW_COUNT = 3;

/**
 * Compact dashboard preview of the canonical Student Events adapter
 * (GET /api/v1/student/events, built in S4 over published
 * `industry_workshops`). Shows a few real upcoming events and links to
 * /student/events. Only actual event records are rendered — no fabricated
 * cards, no invented registration state. Self-contained error handling.
 */
export function DashboardAnnouncements() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listEvents()
      .then(({ events }) => {
        if (!cancelled) setState({ status: "ready", events });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const events = state.status === "ready" ? state.events.slice(0, PREVIEW_COUNT) : [];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Upcoming Events</CardTitle>
        <CardAction>
          <Button
            variant="ghost"
            size="sm"
            render={<Link href="/student/events" />}
            nativeButton={false}
          >
            View all
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent>
        {state.status === "loading" && (
          <div className="space-y-2" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        )}

        {state.status === "error" && (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <AlertCircle className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">Couldn&apos;t load upcoming events.</p>
            <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
              Try again
            </Button>
          </div>
        )}

        {state.status === "ready" && events.length === 0 && (
          <div className="flex flex-col items-center gap-2 rounded-lg border border-dashed py-8 text-center">
            <CalendarDays className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm font-medium">Nothing scheduled</p>
            <p className="text-xs text-muted-foreground">
              Workshops published by industry partners will appear here.
            </p>
          </div>
        )}

        {state.status === "ready" && events.length > 0 && (
          <div className="space-y-1.5">
            {events.map((event) => (
              <Link
                key={event.id}
                href={`/student/events/${event.id}`}
                className="flex items-start gap-2 rounded-lg border px-2.5 py-2 text-sm transition-colors hover:bg-muted"
              >
                <CalendarDays
                  className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{event.title}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {event.start_date
                      ? new Date(event.start_date).toLocaleDateString()
                      : "Date to be announced"}
                    {event.work_mode ? ` · ${STUDENT_EVENT_WORK_MODE_LABELS[event.work_mode]}` : ""}
                  </span>
                </span>
                <ArrowRight
                  className="mt-0.5 size-3.5 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
