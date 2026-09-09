"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowUpRight, Ban, FileText, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApplicationStatusBadge } from "@/components/student/opportunities/application-status-badge";
import { ApiError } from "@/lib/api";
import { listMyApplications, withdrawApplication } from "@/lib/student/opportunities";
import { listMyInternshipWorkspaces } from "@/lib/student/internship-workspace";
import { listMyJobTraining } from "@/lib/student/job-training";
import { INTERVIEW_LOCATION_LABELS, INTERVIEW_MODE_LABELS } from "@/types/interview";
import type { InternshipWorkspaceSummary } from "@/types/internship-workspace";
import type { JobTrainingEnrollmentSummary } from "@/types/job-training";
import {
  canWithdrawApplication,
  type SourceType,
  type StudentApplication,
  type StudentApplicationInterview,
} from "@/types/student-opportunity";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | {
      status: "ready";
      applications: StudentApplication[];
      workspacesByApplication: Record<string, InternshipWorkspaceSummary>;
      jobTrainingByApplication: Record<string, JobTrainingEnrollmentSummary>;
    };

const TYPE_LABEL: Record<SourceType, string> = { JOB: "Job", INTERNSHIP: "Internship" };
const DETAIL_BASE: Record<SourceType, string> = {
  INTERNSHIP: "/student/internships",
  JOB: "/student/jobs",
};

/** GET /api/v1/student/applications -- the authenticated student's own
 * applications only. Also loads (best effort) the student's internship
 * workspaces AND job training enrollments so a SELECTED application can
 * link straight to the right place: a selected internship -> its
 * Internship Workspace, a selected job with a training program -> its Job
 * Training. Neither industry-only provisioning endpoint is called here.
 * A selected job WITHOUT an enrollment shows no CTA (no fabricated
 * "Start Training"). */
type Feedback = { kind: "success" | "error"; message: string };

export function MyApplicationsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  // Withdrawal: the row whose confirmation dialog is open, whether the
  // request is in flight, and the last success/error banner.
  const [withdrawTarget, setWithdrawTarget] = useState<StudentApplication | null>(null);
  const [withdrawPending, setWithdrawPending] = useState(false);
  const [feedback, setFeedback] = useState<Feedback | null>(null);

  async function handleWithdrawConfirm() {
    const target = withdrawTarget;
    if (!target || withdrawPending) return;
    setWithdrawPending(true);
    setFeedback(null);
    try {
      const updated = await withdrawApplication(target.id);
      setState((s) =>
        s.status === "ready"
          ? { ...s, applications: s.applications.map((a) => (a.id === updated.id ? updated : a)) }
          : s,
      );
      setFeedback({
        kind: "success",
        message: target.opportunity?.title
          ? `Withdrew your application for “${target.opportunity.title}”.`
          : "Your application has been withdrawn.",
      });
    } catch (err) {
      setFeedback({
        kind: "error",
        message:
          err instanceof ApiError
            ? err.message
            : "Could not withdraw this application. Please try again.",
      });
    } finally {
      setWithdrawPending(false);
      setWithdrawTarget(null);
    }
  }

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { applications } = await listMyApplications();

        const [workspacesByApplication, jobTrainingByApplication] = await Promise.all([
          listMyInternshipWorkspaces()
            .then((r) =>
              Object.fromEntries(r.workspaces.map((w) => [w.application_id, w])),
            )
            .catch(() => ({}) as Record<string, InternshipWorkspaceSummary>),
          listMyJobTraining()
            .then((r) =>
              Object.fromEntries(r.enrollments.map((e) => [e.application_id, e])),
            )
            .catch(() => ({}) as Record<string, JobTrainingEnrollmentSummary>),
        ]);

        if (cancelled) return;
        setState({
          status: "ready",
          applications,
          workspacesByApplication,
          jobTrainingByApplication,
        });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your applications."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (state.status === "loading") {
    return (
      <div
        className="h-40 animate-pulse rounded-lg bg-muted"
        aria-busy="true"
        aria-label="Loading applications"
      />
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load your applications.</p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (state.applications.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
          <FileText className="size-8" />
          <p className="font-medium text-foreground">No applications yet</p>
          <p className="text-sm">Browse internships and jobs, and apply to track them here.</p>
          <Button size="sm" render={<Link href="/student/internships" />} nativeButton={false}>
            Browse Internships
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardContent className="space-y-4">
        {feedback ? (
          feedback.kind === "success" ? (
            <FormSuccess message={feedback.message} />
          ) : (
            <FormError message={feedback.message} />
          )
        ) : null}

        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Opportunity</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Applied on</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Next steps</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {state.applications.map((app) => {
              const opp = app.opportunity;
              const type = opp?.source_type ?? app.opportunity_type;
              return (
                <TableRow key={app.id}>
                  <TableCell className="font-medium">
                    {opp?.title && opp.id ? (
                      <Link href={`${DETAIL_BASE[type]}/${opp.id}`} className="hover:underline">
                        {opp.title}
                      </Link>
                    ) : (
                      opp?.title ?? "—"
                    )}
                  </TableCell>
                  <TableCell>
                    <Badge variant="secondary">{TYPE_LABEL[type]}</Badge>
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {opp?.industry?.company_name ?? "—"}
                  </TableCell>
                  <TableCell className="text-muted-foreground">
                    {app.applied_at ? new Date(app.applied_at).toLocaleDateString() : "—"}
                  </TableCell>
                  <TableCell>
                    <ApplicationStatusBadge status={app.status} />
                  </TableCell>
                  <TableCell>
                    <NextStepCell
                      application={app}
                      workspace={state.workspacesByApplication[app.id]}
                      jobTraining={state.jobTrainingByApplication[app.id]}
                      onWithdraw={setWithdrawTarget}
                    />
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>

      <ConfirmationDialog
        open={withdrawTarget !== null}
        onOpenChange={(open) => {
          if (!open) setWithdrawTarget(null);
        }}
        title="Withdraw this application?"
        description={
          withdrawTarget?.opportunity?.title
            ? `Your application for “${withdrawTarget.opportunity.title}” will be marked as withdrawn and will no longer be considered by the company. This can’t be undone.`
            : "This application will be marked as withdrawn and will no longer be considered by the company. This can’t be undone."
        }
        confirmLabel="Withdraw application"
        cancelLabel="Keep application"
        destructive
        loading={withdrawPending}
        onConfirm={handleWithdrawConfirm}
      />
    </Card>
  );
}

function NextStepCell({
  application,
  workspace,
  jobTraining,
  onWithdraw,
}: {
  application: StudentApplication;
  workspace: InternshipWorkspaceSummary | undefined;
  jobTraining: JobTrainingEnrollmentSummary | undefined;
  onWithdraw: (application: StudentApplication) => void;
}) {
  const type = application.opportunity?.source_type ?? application.opportunity_type;
  const isSelected = application.status === "SELECTED";
  const withdrawable = canWithdrawApplication(application.status);

  // ---- Withdrawn: the student pulled out. Never a bare "—". ----
  if (application.status === "WITHDRAWN") {
    return (
      <span className="text-sm text-muted-foreground">You withdrew this application.</span>
    );
  }

  // ---- Interview scheduled: render the live (SCHEDULED) interview, or a
  // "being scheduled" note when the application is at INTERVIEW_SCHEDULED
  // but has no live interview row yet (a manual status move, or the
  // interview was cancelled/completed). A withdraw action sits below it. ----
  if (application.status === "INTERVIEW_SCHEDULED") {
    return (
      <div className="space-y-2">
        {application.interview ? (
          <InterviewDetails interview={application.interview} />
        ) : (
          <InterviewPending />
        )}
        <WithdrawButton onClick={() => onWithdraw(application)} />
      </div>
    );
  }

  // ---- Selected JOB: Job Training, but ONLY when an enrollment exists ----
  if (isSelected && type === "JOB") {
    if (jobTraining) {
      return (
        <Button
          size="sm"
          variant="outline"
          render={<Link href={`/student/job-training/${jobTraining.enrollment_id}`} />}
          nativeButton={false}
        >
          Open Job Training <ArrowUpRight className="size-3.5" />
        </Button>
      );
    }
    return (
      <span className="text-sm text-muted-foreground">
        Job training isn&apos;t available for this role.
      </span>
    );
  }

  // ---- Selected INTERNSHIP: existing Internship Workspace behaviour ----
  if (isSelected && type === "INTERNSHIP") {
    if (workspace) {
      return (
        <Button
          size="sm"
          variant="outline"
          render={<Link href={`/student/my-internships/${workspace.id}`} />}
          nativeButton={false}
        >
          Open Internship Workspace <ArrowUpRight className="size-3.5" />
        </Button>
      );
    }

    const workMode = application.opportunity?.work_mode;
    if (workMode && workMode !== "REMOTE" && workMode !== "HYBRID") {
      return (
        <span className="text-sm text-muted-foreground">
          On-site internship — no online workspace.
        </span>
      );
    }

    return (
      <span className="text-sm text-muted-foreground">
        Internship workspace is not available yet.
      </span>
    );
  }

  // ---- Active candidate application (APPLIED / UNDER_REVIEW / SHORTLISTED):
  // the only "next step" the student controls is withdrawing. ----
  if (withdrawable) {
    return <WithdrawButton onClick={() => onWithdraw(application)} />;
  }

  // REJECTED and any other non-actionable state.
  return <span className="text-muted-foreground">—</span>;
}

/** Small, low-emphasis trigger that opens the withdrawal confirmation
 * dialog. Never mutates on its own — the parent owns the dialog + request. */
function WithdrawButton({ onClick }: { onClick: () => void }) {
  return (
    <Button
      variant="ghost"
      size="sm"
      className="h-7 gap-1 px-1.5 text-xs text-muted-foreground hover:text-destructive"
      onClick={onClick}
    >
      <Ban className="size-3.5" aria-hidden="true" /> Withdraw
    </Button>
  );
}

/** An http(s) URL string, or null. Guards the "Join meeting" link so an
 * arbitrary `location` value is only ever rendered as an anchor when it is
 * genuinely a web URL — everything else falls back to plain text. */
function asHttpUrl(value: string | null): string | null {
  if (!value) return null;
  try {
    const url = new URL(value);
    return url.protocol === "http:" || url.protocol === "https:" ? url.toString() : null;
  } catch {
    return null;
  }
}

/** INTERVIEW_SCHEDULED with a live SCHEDULED interview row. Renders the
 * date/time/duration/mode and, for an ONLINE interview whose `location` is
 * a URL, a "Join meeting" link. `interviews.notes` is Industry-private and
 * is not part of this data at all. */
function InterviewDetails({ interview }: { interview: StudentApplicationInterview }) {
  const start = new Date(interview.scheduled_at);
  if (Number.isNaN(start.getTime())) {
    // Malformed/missing scheduled_at — never render "Invalid Date".
    return <InterviewPending />;
  }

  const end = new Date(start.getTime() + interview.duration_minutes * 60_000);
  const dateLabel = start.toLocaleDateString(undefined, {
    day: "numeric",
    month: "long",
    year: "numeric",
  });
  const timeLabel = `${start.toLocaleTimeString(undefined, {
    hour: "numeric",
    minute: "2-digit",
  })} – ${end.toLocaleTimeString(undefined, { hour: "numeric", minute: "2-digit" })}`;
  const modeLabel = INTERVIEW_MODE_LABELS[interview.mode] ?? interview.mode;
  const locationLabel = INTERVIEW_LOCATION_LABELS[interview.mode] ?? "Location";
  const meetingUrl = interview.mode === "ONLINE" ? asHttpUrl(interview.location) : null;

  return (
    <div className="space-y-0.5 text-sm">
      <p className="font-medium text-foreground">Interview scheduled</p>
      <p className="text-muted-foreground">
        Date: <span className="text-foreground">{dateLabel}</span>
      </p>
      <p className="text-muted-foreground">
        Time: <span className="text-foreground">{timeLabel}</span>
      </p>
      <p className="text-muted-foreground">
        Duration:{" "}
        <span className="text-foreground">{interview.duration_minutes} minutes</span>
      </p>
      <p className="text-muted-foreground">
        Mode: <span className="text-foreground">{modeLabel}</span>
      </p>
      {meetingUrl ? (
        <p className="text-muted-foreground">
          {locationLabel}:{" "}
          <a
            href={meetingUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-0.5 font-medium text-primary hover:underline"
          >
            Join meeting <ArrowUpRight className="size-3.5" />
          </a>
        </p>
      ) : interview.location ? (
        <p className="text-muted-foreground">
          {locationLabel}: <span className="text-foreground">{interview.location}</span>
        </p>
      ) : null}
    </div>
  );
}

/** INTERVIEW_SCHEDULED without a live interview row — a manual status move,
 * or the interview was cancelled/completed. No fake date, no broken card. */
function InterviewPending() {
  return (
    <span className="text-sm text-muted-foreground">
      Your interview is being scheduled — check back soon.
    </span>
  );
}
