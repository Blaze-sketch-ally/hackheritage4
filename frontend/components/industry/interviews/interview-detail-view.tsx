"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { cancelInterview, completeInterview, getInterview } from "@/lib/industry/interviews";
import { applicantRef, OPPORTUNITY_TYPE_LABELS } from "@/types/application";
import { INTERVIEW_LOCATION_LABELS, INTERVIEW_MODE_LABELS, type Interview } from "@/types/interview";
import { InterviewStatusBadge } from "@/components/industry/interviews/interview-status-badge";
import { InterviewFormDialog } from "@/components/industry/interviews/interview-form-dialog";
import { formatInterviewWhen } from "@/components/industry/interviews/interview-card";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; interview: Interview };

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  const empty = children == null || children === "";
  return (
    <div className="space-y-0.5">
      <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className={empty ? "text-sm text-muted-foreground/60" : "text-sm"}>
        {empty ? "Not set" : children}
      </dd>
    </div>
  );
}

export function InterviewDetailView({ interviewId }: { interviewId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [pending, setPending] = useState(false);
  const [confirming, setConfirming] = useState<"complete" | "cancel" | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getInterview(interviewId)
      .then((interview) => {
        if (!cancelled) setState({ status: "ready", interview });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this interview."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [interviewId, reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function runAction(action: "complete" | "cancel") {
    setConfirming(null);
    setPending(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await (action === "complete" ? completeInterview : cancelInterview)(
        interviewId,
      );
      setState({ status: "ready", interview: updated });
      setActionSuccess(action === "complete" ? "Interview marked completed." : "Interview cancelled.");
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-6">
      <Link
        href="/industry/interviews"
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> All interviews
      </Link>

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {state.error.status === 404
                  ? "This interview doesn't exist or isn't one of yours."
                  : state.error.status === 401
                    ? "Your session has expired. Please sign in again."
                    : "Could not load this interview."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status === 404 ? (
              <Button variant="outline" size="sm" render={<Link href="/industry/interviews" />}>
                Back to interviews
              </Button>
            ) : state.error.status !== 401 ? (
              <Button variant="outline" size="sm" onClick={reload}>
                <RefreshCw className="size-3.5" /> Try again
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? (
        <>
          <FormError message={actionError} />
          <FormSuccess message={actionSuccess} />

          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0 space-y-1">
              <div className="flex flex-wrap items-center gap-2">
                <h1 className="text-xl font-semibold">
                  {applicantRef(state.interview.student_id)}
                </h1>
                <InterviewStatusBadge status={state.interview.status} />
              </div>
              <p className="text-xs text-muted-foreground">
                {formatInterviewWhen(state.interview.scheduled_at)} ·{" "}
                {state.interview.duration_minutes} minutes
              </p>
            </div>
            {state.interview.status === "SCHEDULED" ? (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => setRescheduleOpen(true)}
                  disabled={pending}
                >
                  Reschedule
                </Button>
                <Button size="sm" onClick={() => setConfirming("complete")} disabled={pending}>
                  Mark complete
                </Button>
                <Button
                  size="sm"
                  variant="ghost"
                  onClick={() => setConfirming("cancel")}
                  disabled={pending}
                >
                  Cancel
                </Button>
              </div>
            ) : null}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Interview</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-4 sm:grid-cols-2">
                <Detail label="When">{formatInterviewWhen(state.interview.scheduled_at)}</Detail>
                <Detail label="Duration">{state.interview.duration_minutes} minutes</Detail>
                <Detail label="Format">{INTERVIEW_MODE_LABELS[state.interview.mode]}</Detail>
                <Detail label={INTERVIEW_LOCATION_LABELS[state.interview.mode]}>
                  {state.interview.location}
                </Detail>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Candidate &amp; opportunity</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <dl className="grid gap-4 sm:grid-cols-2">
                <Detail label="Applicant reference">
                  {applicantRef(state.interview.student_id)}
                </Detail>
                <Detail label="Opportunity">
                  {state.interview.opportunity ? (
                    state.interview.opportunity.title
                  ) : state.interview.opportunity_type ? (
                    OPPORTUNITY_TYPE_LABELS[state.interview.opportunity_type]
                  ) : null}
                </Detail>
                <Detail label="Application">
                  <Link
                    href={`/industry/applicants/${state.interview.application_id}`}
                    className="text-indigo-600 hover:underline dark:text-indigo-400"
                  >
                    View application
                  </Link>
                </Detail>
              </dl>
              <p className="text-xs text-muted-foreground">
                Applicant profile details are not available to companies at this stage of the portal.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Notes</CardTitle>
            </CardHeader>
            <CardContent>
              {state.interview.notes ? (
                <p className="text-sm whitespace-pre-line">{state.interview.notes}</p>
              ) : (
                <p className="text-sm text-muted-foreground/70">No notes added.</p>
              )}
            </CardContent>
          </Card>

          <InterviewFormDialog
            open={rescheduleOpen}
            onOpenChange={setRescheduleOpen}
            mode="reschedule"
            interview={state.interview}
            onSubmitted={(interview) => {
              setState({ status: "ready", interview });
              setActionSuccess("Interview updated.");
            }}
          />

          <ConfirmationDialog
            open={confirming !== null}
            onOpenChange={(open) => !open && setConfirming(null)}
            title={
              confirming === "complete"
                ? "Mark this interview as completed?"
                : "Cancel this interview?"
            }
            description={
              confirming === "complete"
                ? "Use this once the interview has taken place."
                : "The interview will be marked cancelled. The candidate's application status is left unchanged."
            }
            confirmLabel={confirming === "complete" ? "Mark complete" : "Cancel interview"}
            destructive={confirming === "cancel"}
            loading={pending}
            onConfirm={() => confirming && runAction(confirming)}
          />
        </>
      ) : null}
    </div>
  );
}
