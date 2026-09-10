"use client";

import { useEffect, useState } from "react";
import { Info, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Loading } from "@/components/common/loading";
import { ErrorState } from "@/components/common/error-state";
import { ApiError } from "@/lib/api";
import { getInstitutionEventOverview, getInstitutionEvents } from "@/lib/institution/events";
import type { EventListResponse, EventOverviewResponse } from "@/types/institution-event";
import { EventKpis } from "@/components/institution/events/event-kpis";
import { EventsTable } from "@/components/institution/events/events-table";
import { EventForm } from "@/components/institution/events/event-form";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; list: EventListResponse; overview: EventOverviewResponse };

/**
 * Institution Events, Seminars & Workshops (Phase 10): directory + KPIs
 * on one page. Two independent server-side aggregation calls, same
 * architecture as the rest of the Institution module.
 */
export function InstitutionEventsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getInstitutionEvents(), getInstitutionEventOverview()])
      .then(([list, overview]) => {
        if (!cancelled) setState({ status: "ready", list, overview });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load events."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  function handleSaved() {
    setFormOpen(false);
    reload();
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Events, Seminars & Workshops</h1>
          <p className="text-sm text-muted-foreground">
            Seminars, workshops, guest lectures and other sessions relevant to your institution.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="size-4" /> Create Event
        </Button>
      </div>

      {state.status === "loading" ? <Loading label="Loading events…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={state.error.status === 401 ? "Your session has expired. Please sign in again." : state.error.message}
          onRetry={state.error.status !== 401 ? reload : undefined}
        />
      ) : null}

      {state.status === "ready" ? (
        <div className="space-y-6">
          <EventKpis kpis={state.overview.kpis} />

          <EventsTable
            events={state.list.events}
            typeOptions={state.list.type_options}
            statusOptions={state.list.status_options}
            modeOptions={state.list.mode_options}
          />

          <div className="space-y-2">
            {[state.overview.tenancy_note, state.list.registration_note].map((note) => (
              <p key={note} className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
                <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
                {note}
              </p>
            ))}
          </div>
        </div>
      ) : null}

      <EventForm open={formOpen} onOpenChange={setFormOpen} onSaved={handleSaved} />
    </div>
  );
}
