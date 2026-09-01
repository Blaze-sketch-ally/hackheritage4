"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, CalendarClock, Plus, RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { Filters } from "@/components/common/filters";
import { SearchBar } from "@/components/common/search-bar";
import { ApiError } from "@/lib/api";
import { getApplications } from "@/lib/industry/applications";
import { cancelInterview, completeInterview, getInterviews } from "@/lib/industry/interviews";
import { applicantRef, type Application } from "@/types/application";
import {
  INTERVIEW_STATUS_LABELS,
  INTERVIEW_STATUSES,
  type Interview,
} from "@/types/interview";
import { InterviewCard } from "@/components/industry/interviews/interview-card";
import { InterviewFormDialog } from "@/components/industry/interviews/interview-form-dialog";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; interviews: Interview[]; applications: Application[] };

type LifecycleAction = "complete" | "cancel";

const ACTION_COPY: Record<
  LifecycleAction,
  { title: string; description: string; confirm: string; destructive: boolean; done: string }
> = {
  complete: {
    title: "Mark this interview as completed?",
    description: "Use this once the interview has taken place.",
    confirm: "Mark complete",
    destructive: false,
    done: "Interview marked completed.",
  },
  cancel: {
    title: "Cancel this interview?",
    description:
      "The interview will be marked cancelled. The candidate's application status is left unchanged.",
    confirm: "Cancel interview",
    destructive: true,
    done: "Interview cancelled.",
  },
};

const RUNNERS: Record<LifecycleAction, (id: string) => Promise<Interview>> = {
  complete: completeInterview,
  cancel: cancelInterview,
};

const ELIGIBLE_APP_STATUSES = new Set(["SHORTLISTED", "INTERVIEW_SCHEDULED"]);

export function InterviewsListView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [rescheduling, setRescheduling] = useState<Interview | null>(null);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<{ id: string; action: LifecycleAction } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getInterviews(), getApplications()])
      .then(([{ interviews }, { applications }]) => {
        if (!cancelled) setState({ status: "ready", interviews, applications });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your interviews."),
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

  const eligibleApplications = useMemo(() => {
    if (state.status !== "ready") return [];
    const withLiveInterview = new Set(
      state.interviews.filter((i) => i.status === "SCHEDULED").map((i) => i.application_id),
    );
    return state.applications.filter(
      (a) => ELIGIBLE_APP_STATUSES.has(a.status) && !withLiveInterview.has(a.id),
    );
  }, [state]);

  const visible = useMemo(() => {
    if (state.status !== "ready") return [];
    const query = search.trim().toLowerCase();
    return state.interviews.filter((iv) => {
      const matchesStatus = statusFilter === "all" || iv.status === statusFilter;
      const haystack =
        `${iv.opportunity?.title ?? ""} ${applicantRef(iv.student_id)}`.toLowerCase();
      const matchesSearch = !query || haystack.includes(query);
      return matchesStatus && matchesSearch;
    });
  }, [state, search, statusFilter]);

  function upsertInterview(updated: Interview) {
    setState((prev) => {
      if (prev.status !== "ready") return prev;
      const exists = prev.interviews.some((i) => i.id === updated.id);
      const interviews = exists
        ? prev.interviews.map((i) => (i.id === updated.id ? updated : i))
        : [...prev.interviews, updated];
      // Keep the underlying application's status in sync when scheduling
      // advanced it to INTERVIEW_SCHEDULED.
      const applications = prev.applications.map((a) =>
        a.id === updated.application_id && a.status === "SHORTLISTED"
          ? { ...a, status: "INTERVIEW_SCHEDULED" as const }
          : a,
      );
      return { ...prev, interviews, applications };
    });
  }

  async function runAction(id: string, action: LifecycleAction) {
    setConfirming(null);
    setPendingId(id);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await RUNNERS[action](id);
      upsertInterview(updated);
      setActionSuccess(ACTION_COPY[action].done);
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setPendingId(null);
    }
  }

  const statusOptions = [
    { value: "all", label: "All statuses" },
    ...INTERVIEW_STATUSES.map((s) => ({ value: s, label: INTERVIEW_STATUS_LABELS[s] })),
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Interviews</h1>
          <p className="text-sm text-muted-foreground">
            Schedule and track interviews for your shortlisted candidates.
          </p>
        </div>
        <Button
          onClick={() => setScheduleOpen(true)}
          disabled={state.status !== "ready"}
        >
          <Plus className="size-4" /> Schedule interview
        </Button>
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading your interviews…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {state.error.status === 401
                  ? "Your session has expired. Please sign in again."
                  : "Could not load your interviews."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status !== 401 ? (
              <Button variant="outline" size="sm" onClick={reload}>
                <RefreshCw className="size-3.5" /> Try again
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? (
        state.interviews.length === 0 ? (
          <EmptyState
            icon={CalendarClock}
            title="No interviews scheduled"
            description={
              eligibleApplications.length > 0
                ? "Schedule an interview for one of your shortlisted candidates."
                : "Shortlist a candidate first, then schedule their interview here."
            }
            actionLabel={eligibleApplications.length > 0 ? "Schedule interview" : undefined}
            onAction={eligibleApplications.length > 0 ? () => setScheduleOpen(true) : undefined}
          />
        ) : (
          <>
            <div className="flex flex-col gap-3 sm:flex-row">
              <SearchBar
                value={search}
                onChange={setSearch}
                placeholder="Search by candidate or opportunity..."
                aria-label="Search interviews"
              />
              <Filters
                value={statusFilter}
                onChange={setStatusFilter}
                options={statusOptions}
                aria-label="Filter by status"
              />
            </div>

            {visible.length === 0 ? (
              <EmptyState icon={Search} title="No interviews match your filters" />
            ) : (
              <div className="space-y-3">
                {visible.map((interview) => (
                  <InterviewCard
                    key={interview.id}
                    interview={interview}
                    pending={pendingId === interview.id}
                    onReschedule={() => setRescheduling(interview)}
                    onComplete={() => setConfirming({ id: interview.id, action: "complete" })}
                    onCancel={() => setConfirming({ id: interview.id, action: "cancel" })}
                  />
                ))}
              </div>
            )}
          </>
        )
      ) : null}

      <InterviewFormDialog
        open={scheduleOpen}
        onOpenChange={setScheduleOpen}
        mode="schedule"
        eligibleApplications={eligibleApplications}
        onSubmitted={(interview) => {
          upsertInterview(interview);
          setActionSuccess("Interview scheduled.");
        }}
      />

      <InterviewFormDialog
        open={rescheduling !== null}
        onOpenChange={(open) => !open && setRescheduling(null)}
        mode="reschedule"
        interview={rescheduling ?? undefined}
        onSubmitted={(interview) => {
          upsertInterview(interview);
          setActionSuccess("Interview updated.");
        }}
      />

      <ConfirmationDialog
        open={!!confirming}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={confirming ? ACTION_COPY[confirming.action].title : ""}
        description={confirming ? ACTION_COPY[confirming.action].description : undefined}
        confirmLabel={confirming ? ACTION_COPY[confirming.action].confirm : "Confirm"}
        destructive={confirming ? ACTION_COPY[confirming.action].destructive : false}
        loading={!!pendingId}
        onConfirm={() => confirming && runAction(confirming.id, confirming.action)}
      />
    </div>
  );
}
