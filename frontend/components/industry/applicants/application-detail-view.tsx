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
import { ApplicationStatusActions } from "@/components/industry/applicants/application-status-actions";
import { ApplicationStatusBadge } from "@/components/industry/applicants/application-status-badge";
import { MatchScore } from "@/components/industry/match-score";

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

export function ApplicationDetailView({ applicationId }: { applicationId: string }) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  const [pending, setPending] = useState(false);
  const [confirming, setConfirming] = useState<IndustrySettableStatus | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

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

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function runTransition(target: IndustrySettableStatus) {
    setConfirming(null);
    setPending(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await updateApplicationStatus(applicationId, target);
      setState({ status: "ready", application: updated });
      setActionSuccess(`Application moved to “${APPLICATION_STATUS_LABELS[target]}”.`);
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
                onPick={(target) => setConfirming(target)}
              />
            </div>
          </div>

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
