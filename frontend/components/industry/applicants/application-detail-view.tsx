"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertCircle, ArrowLeft, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { getApplication, updateApplicationStatus } from "@/lib/industry/applications";
import {
  APPLICATION_STATUS_LABELS,
  OPPORTUNITY_TYPE_LABELS,
  TRANSITION_LABELS,
  applicantDisplayName,
  applicantRef,
  type Application,
  type IndustrySettableStatus,
} from "@/types/application";
import { ApplicationInternshipWorkspacePanel } from "@/components/industry/applicants/application-internship-workspace-panel";
import { ApplicationJobTrainingPanel } from "@/components/industry/applicants/application-job-training-panel";
import { ApplicationStatusActions } from "@/components/industry/applicants/application-status-actions";
import { ApplicationStatusBadge } from "@/components/industry/applicants/application-status-badge";
import { formatInterviewWhen } from "@/components/industry/interviews/interview-card";
import { InterviewFormDialog } from "@/components/industry/interviews/interview-form-dialog";
import { InterviewStatusBadge } from "@/components/industry/interviews/interview-status-badge";
import { MatchScore } from "@/components/industry/match-score";
import { getInterviews } from "@/lib/industry/interviews";
import { INTERVIEW_MODE_LABELS, type Interview } from "@/types/interview";

type InterviewLoadState =
  | { status: "loading" }
  | { status: "none" }
  | { status: "error" }
  | { status: "ready"; interview: Interview };

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; application: Application };

function formatDate(value: string | null): string {
  if (!value) return "Not set";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

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

/** The persisted interview for an INTERVIEW_SCHEDULED application, or an
 * honest fallback — never a crash — when the status says a real interview
 * should exist but none was found (e.g. old/test data with no
 * `interviews` row). Deliberately shows only public-safe fields (when,
 * duration, mode, location, status) — never `interview.notes`, which is
 * industry-private prep text with no place on this shared applicant view. */
function InterviewCard({ interviewState }: { interviewState: InterviewLoadState }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Interview</CardTitle>
      </CardHeader>
      <CardContent>
        {interviewState.status === "loading" ? (
          <p className="text-sm text-muted-foreground" aria-busy="true">
            Checking interview details…
          </p>
        ) : null}

        {interviewState.status === "error" ? (
          <p className="text-sm text-muted-foreground">
            Could not load interview details right now.
          </p>
        ) : null}

        {interviewState.status === "none" ? (
          <p className="text-sm text-muted-foreground">
            Interview details are not available for this application.
          </p>
        ) : null}

        {interviewState.status === "ready" ? (
          <div className="space-y-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <p className="text-sm font-medium">
                {formatInterviewWhen(interviewState.interview.scheduled_at)} ·{" "}
                {interviewState.interview.duration_minutes} minutes
              </p>
              <InterviewStatusBadge status={interviewState.interview.status} />
            </div>
            <p className="text-sm text-muted-foreground">
              {INTERVIEW_MODE_LABELS[interviewState.interview.mode]}
              {interviewState.interview.location ? ` · ${interviewState.interview.location}` : ""}
            </p>
            <Button
              size="sm"
              variant="outline"
              render={<Link href={`/industry/interviews/${interviewState.interview.id}`} />}
              nativeButton={false}
            >
              View Interview
            </Button>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}

export function ApplicationDetailView({ applicationId }: { applicationId: string }) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  const [pending, setPending] = useState(false);
  const [confirming, setConfirming] = useState<IndustrySettableStatus | null>(null);
  // Scheduling an interview needs real date/time/mode/location, not a bare
  // status PATCH -- "Schedule interview" opens the real scheduling dialog
  // (same one Interview Panel uses) instead of the generic confirm dialog
  // every other transition uses. See recruitment-applications.tsx's
  // identical handlePick for the Applicants/Shortlisted-list version of
  // this same fix.
  const [scheduleOpen, setScheduleOpen] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  // Starts as "loading" unconditionally -- harmless, since InterviewCard is
  // only ever mounted (see the render call site below) when
  // applicationStatus is already INTERVIEW_SCHEDULED, the one case this
  // state is ever actually displayed.
  const [interviewState, setInterviewState] = useState<InterviewLoadState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    getApplication(applicationId)
      .then((application) => {
        if (!cancelled) setState({ status: "ready", application });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this application."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId, reloadKey]);

  // The persisted interview for this application, if one exists -- shown
  // as a card below instead of forcing the recruiter to leave and re-find
  // this same candidate in Interview Panel. Only fetched once the pipeline
  // has actually reached the point an interview could exist (APPLIED/
  // UNDER_REVIEW/SHORTLISTED never have one -- interview_service only
  // allows creating one from SHORTLISTED onward). Reuses the existing
  // getInterviews({ application_id }) filter; no new backend endpoint.
  // Never rendered outside INTERVIEW_SCHEDULED (see the InterviewCard call
  // site below, gated on the exact same condition) -- this effect simply
  // has no work to do until the status is actually INTERVIEW_SCHEDULED,
  // at which point `interviewState` is already "loading" from its own
  // initial value above; no need to set it again here.
  const applicationStatus = state.status === "ready" ? state.application.status : null;
  useEffect(() => {
    if (applicationStatus !== "INTERVIEW_SCHEDULED") return;
    let cancelled = false;
    getInterviews({ application_id: applicationId })
      .then(({ interviews }) => {
        if (cancelled) return;
        const live = interviews.find((iv) => iv.status === "SCHEDULED") ?? interviews[0] ?? null;
        setInterviewState(live ? { status: "ready", interview: live } : { status: "none" });
      })
      .catch(() => {
        if (cancelled) return;
        setInterviewState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId, applicationStatus]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  function handlePick(target: IndustrySettableStatus) {
    if (target === "INTERVIEW_SCHEDULED") {
      setScheduleOpen(true);
      return;
    }
    setConfirming(target);
  }

  function handleInterviewScheduled() {
    setState((prev) =>
      prev.status === "ready"
        ? { ...prev, application: { ...prev.application, status: "INTERVIEW_SCHEDULED" } }
        : prev,
    );
    setActionSuccess("Interview scheduled.");
  }

  async function runTransition(target: IndustrySettableStatus) {
    setConfirming(null);
    setPending(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await updateApplicationStatus(applicationId, target);
      setState({ status: "ready", application: updated });
      // On SELECTED the backend reports what it provisioned (Internship
      // Workspace / Job Training enrollment) and hands us the exact line
      // to show — we never re-derive provisioning state on the client.
      // The persisted panels below (ApplicationJobTrainingPanel /
      // ApplicationInternshipWorkspacePanel) independently confirm and
      // display the real state once they mount for a SELECTED application
      // — this success message never needs to carry a one-shot link.
      const provisioning = updated.provisioning;
      setActionSuccess(
        provisioning?.message ?? `Application moved to “${APPLICATION_STATUS_LABELS[target]}”.`,
      );
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
        href="/industry/applicants"
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> All applicants
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
                  ? "This application doesn't exist or isn't for one of your postings."
                  : state.error.status === 401
                    ? "Your session has expired. Please sign in again."
                    : "Could not load this application."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status === 404 ? (
              <Button variant="outline" size="sm" render={<Link href="/industry/applicants" />}>
                Back to applicants
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
                  {applicantDisplayName(state.application)}
                </h1>
                <ApplicationStatusBadge status={state.application.status} />
              </div>
              <p className="text-xs text-muted-foreground">
                Applied {formatDate(state.application.applied_at)} · Updated{" "}
                {formatDate(state.application.updated_at)}
              </p>
            </div>
            <div className="flex flex-wrap items-center gap-2">
              <ApplicationStatusActions
                status={state.application.status}
                pending={pending}
                onPick={handlePick}
              />
            </div>
          </div>

          {state.application.status === "INTERVIEW_SCHEDULED" ? (
            <InterviewCard interviewState={interviewState} />
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>Opportunity</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-4 sm:grid-cols-2">
                <Detail label="Type">
                  {OPPORTUNITY_TYPE_LABELS[state.application.opportunity_type]}
                </Detail>
                <Detail label="Posting">
                  {state.application.opportunity ? (
                    <Link
                      href={
                        state.application.opportunity_type === "INTERNSHIP"
                          ? `/industry/internships/${state.application.internship_id}`
                          : `/industry/jobs/${state.application.job_id}`
                      }
                      className="text-indigo-600 hover:underline dark:text-indigo-400"
                    >
                      {state.application.opportunity.title}
                    </Link>
                  ) : (
                    "(posting unavailable)"
                  )}
                </Detail>
                <Detail label="Posting status">
                  {state.application.opportunity?.status ?? null}
                </Detail>
              </dl>
            </CardContent>
          </Card>

          <MatchScore applicationId={state.application.id} />

          {state.application.opportunity_type === "JOB" &&
          state.application.status === "SELECTED" &&
          state.application.job_id ? (
            <ApplicationJobTrainingPanel
              applicationId={state.application.id}
              jobId={state.application.job_id}
              initialProvisioning={state.application.provisioning}
            />
          ) : null}

          {state.application.opportunity_type === "INTERNSHIP" &&
          state.application.status === "SELECTED" &&
          state.application.internship_id ? (
            <ApplicationInternshipWorkspacePanel
              applicationId={state.application.id}
              internshipId={state.application.internship_id}
            />
          ) : null}

          <Card>
            <CardHeader>
              <CardTitle>Applicant</CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <dl className="grid gap-4 sm:grid-cols-2">
                <Detail label="Name">{applicantDisplayName(state.application)}</Detail>
                <Detail label="Applicant reference">
                  {applicantRef(state.application.student_id)}
                </Detail>
                <Detail label="Student ID">
                  <span className="font-mono text-xs break-all">{state.application.student_id}</span>
                </Detail>
              </dl>
              <p className="text-xs text-muted-foreground">
                Further profile details beyond the applicant&apos;s name are not available to
                companies at this stage of the portal.
              </p>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Cover Note</CardTitle>
            </CardHeader>
            <CardContent>
              {state.application.cover_note ? (
                <p className="text-sm whitespace-pre-line">{state.application.cover_note}</p>
              ) : (
                <p className="text-sm text-muted-foreground/70">
                  The applicant did not include a cover note.
                </p>
              )}
            </CardContent>
          </Card>
        </>
      ) : null}

      <ConfirmationDialog
        open={confirming !== null}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={confirming ? `${TRANSITION_LABELS[confirming]} this application?` : ""}
        description={
          confirming === "REJECTED"
            ? "The applicant will see their application marked as rejected."
            : "This updates where the application sits in your recruitment pipeline."
        }
        confirmLabel={confirming ? TRANSITION_LABELS[confirming] : "Confirm"}
        destructive={confirming === "REJECTED"}
        loading={pending}
        onConfirm={() => confirming && runTransition(confirming)}
      />

      <InterviewFormDialog
        open={scheduleOpen}
        onOpenChange={setScheduleOpen}
        mode="schedule"
        eligibleApplications={state.status === "ready" ? [state.application] : []}
        onSubmitted={handleInterviewScheduled}
      />

      {state.status === "ready" ? (
        <p className="text-right">
          <Button variant="ghost" size="sm" onClick={() => router.push("/industry/applicants")}>
            Done
          </Button>
        </p>
      ) : null}
    </div>
  );
}
