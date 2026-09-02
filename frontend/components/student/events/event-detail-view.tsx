"use client";

import { useEffect, useState } from "react";
import { Building2, CalendarDays, Clock, Info, MapPin, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/common/error-state";
import { ApiError } from "@/lib/api";
import { getEvent } from "@/lib/student/events";
import { STUDENT_EVENT_WORK_MODE_LABELS } from "@/types/student-event";
import type { StudentEventDetail } from "@/types/student-event";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string; notFound: boolean }
  | { status: "ready"; event: StudentEventDetail };

export function EventDetailView({ eventId }: { eventId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getEvent(eventId)
      .then((event) => {
        if (!cancelled) setState({ status: "ready", event });
      })
      .catch((err) => {
        if (cancelled) return;
        const apiErr = err instanceof ApiError ? err : null;
        setState({
          status: "error",
          message: apiErr?.message ?? "Could not load this event.",
          notFound: apiErr?.status === 404,
        });
      });
    return () => {
      cancelled = true;
    };
  }, [eventId, reloadKey]);

  if (state.status === "loading") {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading event">
        <Card className="animate-pulse">
          <CardContent className="space-y-2 py-6">
            <div className="h-5 w-1/2 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-2/3 rounded bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <ErrorState
        message={state.notFound ? "This event is not available." : state.message}
        onRetry={
          state.notFound
            ? undefined
            : () => {
                setState({ status: "loading" });
                setReloadKey((k) => k + 1);
              }
        }
      />
    );
  }

  const { event } = state;
  const organizer = event.organizer?.company_name;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-1.5">
            {event.work_mode && (
              <Badge variant="secondary">
                {STUDENT_EVENT_WORK_MODE_LABELS[event.work_mode]}
              </Badge>
            )}
            {event.location && (
              <Badge variant="outline" className="gap-1">
                <MapPin className="size-3" aria-hidden="true" />
                {event.location}
              </Badge>
            )}
          </div>
          <CardTitle className="text-xl">{event.title}</CardTitle>
          {organizer && (
            <p className="flex items-center gap-1 text-sm text-muted-foreground">
              <Building2 className="size-3.5" aria-hidden="true" />
              {organizer}
              {event.organizer?.industry_sector ? ` · ${event.organizer.industry_sector}` : ""}
            </p>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {event.start_date && (
              <span className="flex items-center gap-1">
                <CalendarDays className="size-3.5" aria-hidden="true" />
                Starts {new Date(event.start_date).toLocaleDateString()}
              </span>
            )}
            {event.duration_days != null && (
              <span className="flex items-center gap-1">
                <Clock className="size-3.5" aria-hidden="true" />
                {event.duration_days} day{event.duration_days === 1 ? "" : "s"}
              </span>
            )}
            {event.capacity != null && (
              <span className="flex items-center gap-1">
                <Users className="size-3.5" aria-hidden="true" />
                {event.capacity} place{event.capacity === 1 ? "" : "s"}
              </span>
            )}
            {event.application_deadline && (
              <span className="flex items-center gap-1">
                <CalendarDays className="size-3.5" aria-hidden="true" />
                Register by {new Date(event.application_deadline).toLocaleDateString()}
              </span>
            )}
          </div>

          <p className="text-sm whitespace-pre-wrap text-muted-foreground">{event.description}</p>

          {event.eligibility_criteria && (
            <div>
              <h3 className="text-sm font-medium">Eligibility</h3>
              <p className="text-sm whitespace-pre-wrap text-muted-foreground">
                {event.eligibility_criteria}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {!event.registration_available && (
        <div className="flex items-start gap-2 rounded-lg border border-border/60 bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>
            Online registration for events isn&apos;t available yet. Contact the organiser directly
            if you&apos;d like to take part.
          </span>
        </div>
      )}
    </div>
  );
}
