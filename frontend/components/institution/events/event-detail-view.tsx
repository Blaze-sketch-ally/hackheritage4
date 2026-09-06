"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Info, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { FormError } from "@/components/auth/form-error";
import { ApiError } from "@/lib/api";
import { getInstitutionEvent, updateInstitutionEventStatus } from "@/lib/institution/events";
import type { EventDetail, EventStatus } from "@/types/institution-event";
import { EVENT_STATUS_LABELS, EVENT_TYPE_LABELS } from "@/types/institution-event";
import { EventForm } from "@/components/institution/events/event-form";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; event: EventDetail };

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  PUBLISHED: "default",
  ONGOING: "default",
  COMPLETED: "secondary",
  CANCELLED: "destructive",
  DRAFT: "outline",
};

const NEXT_STATUS: Partial<Record<EventStatus, { label: string; target: EventStatus }>> = {
  DRAFT: { label: "Publish", target: "PUBLISHED" },
  PUBLISHED: { label: "Start (Ongoing)", target: "ONGOING" },
  ONGOING: { label: "Mark Completed", target: "COMPLETED" },
};

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

/** Event Detail (Phase 10, Part 13). Lifecycle actions only render for
 * an institution-organized event (`source === "INSTITUTION"`) that is
 * not in a terminal state -- a platform-wide Industry workshop is
 * strictly read-only here, matching its RLS (no institution write path
 * exists for it at all). */
export function InstitutionEventDetailView({ eventId }: { eventId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [confirmingCancel, setConfirmingCancel] = useState(false);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getInstitutionEvent(eventId)
      .then((event) => {
        if (!cancelled) setState({ status: "ready", event });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({ status: "error", error: err instanceof ApiError ? err : new ApiError(0, "Could not load this event.") });
      });
    return () => {
      cancelled = true;
    };
  }, [eventId, reloadKey]);

  async function transition(target: EventStatus) {
    setPending(true);
    setActionError(null);
    try {
      const updated = await updateInstitutionEventStatus(eventId, target);
      setState({ status: "ready", event: updated });
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setPending(false);
      setConfirmingCancel(false);
    }
  }

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <Button variant="ghost" size="sm" render={<Link href="/institution/events" />}>
        <ArrowLeft className="size-4" /> Back to Events
      </Button>

      {state.status === "loading" ? <Loading label="Loading event…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={state.error.status === 404 ? "This event isn't visible to your institution." : state.error.message}
          onRetry={
            state.error.status !== 401 && state.error.status !== 404
              ? () => {
                  setState({ status: "loading" });
                  setReloadKey((k) => k + 1);
                }
              : undefined
          }
        />
      ) : null}

      {state.status === "ready" ? <Ready event={state.event} onEdit={() => setFormOpen(true)} onTransition={transition} pending={pending} actionError={actionError} onCancel={() => setConfirmingCancel(true)} /> : null}

      {state.status === "ready" ? (
        <EventForm
          open={formOpen}
          onOpenChange={setFormOpen}
          event={state.event.source === "INSTITUTION" ? state.event : undefined}
          onSaved={(updated) => {
            setFormOpen(false);
            setState({ status: "ready", event: updated });
          }}
        />
      ) : null}

      <ConfirmationDialog
        open={confirmingCancel}
        onOpenChange={setConfirmingCancel}
        title="Cancel this event?"
        description="This can't be undone."
        confirmLabel="Cancel Event"
        destructive
        loading={pending}
        onConfirm={() => transition("CANCELLED")}
      />
    </div>
  );
}

function Ready({
  event: e,
  onEdit,
  onTransition,
  onCancel,
  pending,
  actionError,
}: {
  event: EventDetail;
  onEdit: () => void;
  onTransition: (target: EventStatus) => void;
  onCancel: () => void;
  pending: boolean;
  actionError: string | null;
}) {
  const isInstitutionOwned = e.source === "INSTITUTION";
  const next = NEXT_STATUS[e.status as EventStatus];
  const canCancel = isInstitutionOwned && e.status !== "COMPLETED" && e.status !== "CANCELLED";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-xl font-semibold">{e.title}</h1>
            <Badge variant={STATUS_VARIANT[e.status] ?? "outline"}>{EVENT_STATUS_LABELS[e.status] ?? e.status}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {EVENT_TYPE_LABELS[e.event_type] ?? e.event_type}
            {e.company_name ? ` · ${e.company_name}` : ""}
            {e.platform_wide ? " · Industry-hosted (platform-wide)" : ""}
          </p>
        </div>
        {isInstitutionOwned ? (
          <Button variant="outline" size="sm" onClick={onEdit}>
            <Pencil className="size-4" /> Edit
          </Button>
        ) : null}
      </div>

      <FormError message={actionError} />

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Overview</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <p className="text-sm text-muted-foreground sm:col-span-2">{e.description ?? "No description provided."}</p>
          {[
            ["Start", formatDateTime(e.start_at)],
            ["End", formatDateTime(e.end_at)],
            ["Mode", e.mode ?? "—"],
            ["Venue", e.venue ?? "—"],
            ["Registration Deadline", formatDateTime(e.registration_deadline)],
          ].map(([label, value]) => (
            <div key={label as string}>
              <p className="text-xs text-muted-foreground">{label}</p>
              <p className="text-sm font-medium">{value}</p>
            </div>
          ))}
          {e.instructions ? (
            <div className="sm:col-span-2">
              <p className="text-xs text-muted-foreground">Instructions</p>
              <p className="text-sm">{e.instructions}</p>
            </div>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Audience</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {e.target_department_names.length === 0 && e.target_batches.length === 0 ? (
            <p className="text-muted-foreground">All students{e.includes_faculty ? " and faculty" : ""}.</p>
          ) : (
            <>
              {e.target_department_names.length > 0 ? (
                <p>
                  <span className="text-xs text-muted-foreground">Departments: </span>
                  {e.target_department_names.join(", ")}
                </p>
              ) : null}
              {e.target_batches.length > 0 ? (
                <p>
                  <span className="text-xs text-muted-foreground">Batches: </span>
                  {e.target_batches.join(", ")}
                </p>
              ) : null}
              {e.includes_faculty ? <p className="text-xs text-muted-foreground">Also targets faculty.</p> : null}
            </>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Participation</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="flex items-start gap-1.5 text-sm text-muted-foreground">
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            {e.registration_note}
          </p>
        </CardContent>
      </Card>

      {isInstitutionOwned && (next || canCancel) ? (
        <div className="flex flex-wrap items-center gap-2">
          {next ? (
            <Button onClick={() => onTransition(next.target)} disabled={pending}>
              {next.label}
            </Button>
          ) : null}
          {canCancel ? (
            <Button variant="ghost" onClick={onCancel} disabled={pending}>
              Cancel Event
            </Button>
          ) : null}
        </div>
      ) : null}
    </div>
  );
}
