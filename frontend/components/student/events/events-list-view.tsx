"use client";

import { useEffect, useState } from "react";
import { CalendarDays } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/common/error-state";
import { EventCard } from "@/components/student/events/event-card";
import { ApiError } from "@/lib/api";
import { listEvents } from "@/lib/student/events";
import {
  STUDENT_EVENT_WORK_MODES,
  STUDENT_EVENT_WORK_MODE_LABELS,
} from "@/types/student-event";
import type { StudentEventSummary, StudentEventWorkMode } from "@/types/student-event";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; events: StudentEventSummary[] };

/** GET /api/v1/student/events via the FastAPI bridge. Work-mode filter is
 * applied server-side (a small fixed enum); the title search is applied
 * client-side over what came back, mirroring OpportunityListView. */
export function EventsListView() {
  const [workMode, setWorkMode] = useState<StudentEventWorkMode | null>(null);
  const [search, setSearch] = useState("");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listEvents(workMode ? { workMode } : undefined)
      .then(({ events }) => {
        if (!cancelled) setState({ status: "ready", events });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: err instanceof ApiError ? err.message : "Could not load events.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [workMode, reloadKey]);

  const visible =
    state.status === "ready"
      ? state.events.filter((e) =>
          search.trim() ? e.title.toLowerCase().includes(search.trim().toLowerCase()) : true,
        )
      : [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="search"
          aria-label="Search events"
          placeholder="Search events by title..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <div className="flex flex-wrap gap-1.5">
          <Button
            variant={workMode === null ? "default" : "outline"}
            size="sm"
            onClick={() => setWorkMode(null)}
          >
            All
          </Button>
          {STUDENT_EVENT_WORK_MODES.map((mode) => (
            <Button
              key={mode}
              variant={workMode === mode ? "default" : "outline"}
              size="sm"
              onClick={() => setWorkMode(mode)}
            >
              {STUDENT_EVENT_WORK_MODE_LABELS[mode]}
            </Button>
          ))}
        </div>
      </div>

      {state.status === "loading" && <EventsListSkeleton />}

      {state.status === "error" && (
        <ErrorState
          message={state.message}
          onRetry={() => {
            setState({ status: "loading" });
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {state.status === "ready" && visible.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
            <CalendarDays className="size-8" aria-hidden="true" />
            <p className="font-medium text-foreground">
              {state.events.length === 0
                ? "No upcoming events."
                : `No events match "${search.trim()}".`}
            </p>
            <p className="text-sm">
              Events are published by industry partners — check back later.
            </p>
          </CardContent>
        </Card>
      )}

      {state.status === "ready" && visible.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((event) => (
            <EventCard key={event.id} event={event} href={`/student/events/${event.id}`} />
          ))}
        </div>
      )}
    </div>
  );
}

function EventsListSkeleton() {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
      aria-busy="true"
      aria-label="Loading events"
    >
      {[0, 1, 2].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2 py-4">
            <div className="h-4 w-16 rounded bg-muted" />
            <div className="h-5 w-3/4 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
