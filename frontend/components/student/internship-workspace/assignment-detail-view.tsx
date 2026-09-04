"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Loader2, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { SubmissionStatusBadge } from "@/components/common/submission-status-badge";
import { ApiError } from "@/lib/api";
import {
  getMyWorkspaceAssignment,
  submitMyWorkspaceAssignment,
} from "@/lib/student/internship-workspace";
import type {
  CreateSubmissionInput,
  StudentSubmissionReview,
  WorkspaceAssignmentDetail,
  WorkspaceSubmission,
} from "@/types/internship-workspace";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; detail: WorkspaceAssignmentDetail };

function fmt(value: string | null): string {
  if (!value) return "";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}

function needs(kind: string, repoRequired: boolean, liveExpected: boolean) {
  return {
    repo: repoRequired || kind === "REPO" || kind === "LINK" || kind === "MIXED",
    live: liveExpected || kind === "LINK" || kind === "MIXED",
    attachment: kind === "FILE" || kind === "MIXED",
    notes: kind === "TEXT" || kind === "MIXED",
  };
}

function ReviewNote({ review }: { review: StudentSubmissionReview }) {
  return (
    <div className="rounded-md border border-primary/20 bg-primary/[0.03] px-2.5 py-1.5">
      <div className="flex flex-wrap items-center gap-2">
        <SubmissionStatusBadge status={review.verdict} />
        {review.score != null && (
          <span className="text-xs text-muted-foreground">Score: {review.score}</span>
        )}
        {review.reviewed_at ? (
          <span className="text-xs text-muted-foreground">
            Reviewed {fmt(review.reviewed_at)}
          </span>
        ) : null}
      </div>
      {review.feedback ? (
        <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{review.feedback}</p>
      ) : null}
    </div>
  );
}

function AttemptCard({ attempt }: { attempt: WorkspaceSubmission }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-md border px-3 py-2 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <span className="font-medium">Attempt {attempt.attempt_number}</span>
        <SubmissionStatusBadge status={attempt.submission_status} />
        <span className="text-xs text-muted-foreground">{fmt(attempt.submitted_at)}</span>
      </div>
      {attempt.repo_url ? (
        <span className="truncate text-muted-foreground">Repo: {attempt.repo_url}</span>
      ) : null}
      {attempt.live_url ? (
        <span className="truncate text-muted-foreground">Live: {attempt.live_url}</span>
      ) : null}
      {attempt.attachment_url ? (
        <span className="truncate text-muted-foreground">File: {attempt.attachment_url}</span>
      ) : null}
      {attempt.notes ? (
        <span className="whitespace-pre-wrap text-muted-foreground">{attempt.notes}</span>
      ) : null}
      {attempt.reviews.map((r, i) => (
        <ReviewNote key={`${attempt.id}-${i}`} review={r} />
      ))}
    </div>
  );
}

function SubmissionForm({
  detail,
  onSubmit,
}: {
  detail: WorkspaceAssignmentDetail;
  onSubmit: (data: CreateSubmissionInput) => Promise<boolean>;
}) {
  const { assignment } = detail;
  const show = needs(
    assignment.submission_kind,
    assignment.repo_required,
    assignment.live_url_expected,
  );
  const [repoUrl, setRepoUrl] = useState("");
  const [liveUrl, setLiveUrl] = useState("");
  const [attachmentUrl, setAttachmentUrl] = useState("");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  const isResubmission = detail.attempt_count > 0;

  async function submit() {
    setSaving(true);
    const ok = await onSubmit({
      repo_url: repoUrl.trim() || null,
      live_url: liveUrl.trim() || null,
      attachment_url: attachmentUrl.trim() || null,
      notes: notes.trim() || null,
    });
    setSaving(false);
    if (ok) {
      setRepoUrl("");
      setLiveUrl("");
      setAttachmentUrl("");
      setNotes("");
    }
  }

  return (
    <div className="flex flex-col gap-3">
      <p className="text-sm font-medium">
        {isResubmission ? "Submit a new attempt" : "Submit your work"}
      </p>
      {show.repo && (
        <div className="space-y-1.5">
          <Label htmlFor="s-repo">
            Repository URL{assignment.repo_required ? " (required)" : ""}
          </Label>
          <Input
            id="s-repo"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)}
            placeholder="https://github.com/…"
            disabled={saving}
          />
        </div>
      )}
      {show.live && (
        <div className="space-y-1.5">
          <Label htmlFor="s-live">
            Live / deployed URL{assignment.live_url_expected ? " (required)" : ""}
          </Label>
          <Input
            id="s-live"
            value={liveUrl}
            onChange={(e) => setLiveUrl(e.target.value)}
            placeholder="https://…"
            disabled={saving}
          />
        </div>
      )}
      {show.attachment && (
        <div className="space-y-1.5">
          <Label htmlFor="s-file">File / attachment link</Label>
          <Input
            id="s-file"
            value={attachmentUrl}
            onChange={(e) => setAttachmentUrl(e.target.value)}
            placeholder="https://…"
            disabled={saving}
          />
        </div>
      )}
      {show.notes && (
        <div className="space-y-1.5">
          <Label htmlFor="s-notes">Notes</Label>
          <Textarea
            id="s-notes"
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            rows={4}
            disabled={saving}
          />
        </div>
      )}
      <Button className="w-fit" onClick={submit} disabled={saving}>
        {saving && <Loader2 className="size-3.5 animate-spin" />}
        {isResubmission ? "Submit new attempt" : "Submit"}
      </Button>
    </div>
  );
}

/** One assignment in the student's own workspace: the brief, a submission
 * form (when a submission is currently allowed), and the full attempt
 * history. Every submission is an append-only attempt -- a resubmission is
 * a NEW attempt and never changes an earlier one. */
export function AssignmentDetailView({
  workspaceId,
  assignmentId,
}: {
  workspaceId: string;
  assignmentId: string;
}) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [formError, setFormError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  const reload = useCallback(() => {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const detail = await getMyWorkspaceAssignment(workspaceId, assignmentId);
        if (!cancelled) setState({ status: "ready", detail });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this assignment."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, assignmentId, reloadKey]);

  async function handleSubmit(data: CreateSubmissionInput): Promise<boolean> {
    setFormError(null);
    try {
      const detail = await submitMyWorkspaceAssignment(workspaceId, assignmentId, data);
      setState({ status: "ready", detail });
      setSavedAt(Date.now());
      return true;
    } catch (err) {
      setFormError(
        err instanceof Error ? err.message : "Could not submit your work. Please try again.",
      );
      return false;
    }
  }

  if (state.status === "loading") {
    return (
      <div aria-busy="true" aria-label="Loading assignment">
        <Card className="animate-pulse">
          <CardContent className="space-y-2 py-6">
            <div className="h-5 w-1/2 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (state.status === "error") {
    const notFound = state.error.status === 404;
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <p className="font-medium">
            {notFound ? "Assignment not found." : "Could not load this assignment."}
          </p>
          <p className="text-sm text-muted-foreground">{state.error.message}</p>
          {!notFound && (
            <Button variant="outline" size="sm" onClick={reload}>
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const { detail } = state;
  const { assignment } = detail;
  const latest = detail.submissions[0] ?? null;
  const latestReview = latest?.latest_review ?? null;
  const STATUS_LEAD: Record<string, string> = {
    SUBMITTED: "Submitted — awaiting review.",
    UNDER_REVIEW: "Your latest submission is under review.",
    REVISION_REQUESTED: "The reviewer asked for changes before this can be accepted.",
    ACCEPTED: "This assignment has been accepted. Nothing more to do here.",
    REJECTED: "Your latest submission was not accepted.",
  };

  return (
    <div className="flex flex-col gap-5">
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold">{assignment.title}</h1>
          <Badge variant="outline">{assignment.assignment_type}</Badge>
          <Badge variant={assignment.is_required ? "secondary" : "outline"}>
            {assignment.is_required ? "Required" : "Optional"}
          </Badge>
        </div>
        {detail.module.title ? (
          <p className="text-sm text-muted-foreground">{detail.module.title}</p>
        ) : null}
      </div>

      {assignment.description ? (
        <p className="max-w-prose text-sm whitespace-pre-wrap">{assignment.description}</p>
      ) : null}

      {assignment.instructions ? (
        <Card>
          <CardContent className="py-4">
            <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Instructions
            </p>
            <p className="mt-1 text-sm whitespace-pre-wrap">{assignment.instructions}</p>
          </CardContent>
        </Card>
      ) : null}

      <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
        {assignment.due_offset_days != null && (
          <Badge variant="outline">Due day {assignment.due_offset_days}</Badge>
        )}
        {assignment.max_score != null && (
          <Badge variant="outline">Max score {assignment.max_score}</Badge>
        )}
      </div>

      <Card>
        <CardContent className="flex flex-col gap-3 py-4">
          {latest ? (
            <div className="flex flex-wrap items-center gap-2">
              <SubmissionStatusBadge status={latest.submission_status} />
              <span className="text-sm text-muted-foreground">
                {STATUS_LEAD[latest.submission_status] ?? ""}
              </span>
            </div>
          ) : null}

          {latestReview?.feedback ? (
            <div className="rounded-md border border-primary/20 bg-primary/[0.03] px-3 py-2">
              <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Reviewer feedback
              </p>
              <p className="mt-1 text-sm whitespace-pre-wrap">{latestReview.feedback}</p>
              {latestReview.score != null && (
                <p className="mt-1 text-xs text-muted-foreground">
                  Score: {latestReview.score}
                </p>
              )}
            </div>
          ) : null}

          <FormError message={formError} />
          {savedAt && !formError ? <FormSuccess message="Submission received." /> : null}
          {detail.can_submit ? (
            <SubmissionForm detail={detail} onSubmit={handleSubmit} />
          ) : (
            <p className="text-sm text-muted-foreground">
              {detail.submit_blocked_reason ?? "You can't submit to this assignment right now."}
            </p>
          )}
        </CardContent>
      </Card>

      <section className="flex flex-col gap-2">
        <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
          Your attempts ({detail.attempt_count})
        </p>
        {detail.submissions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No attempts yet.</p>
        ) : (
          detail.submissions.map((s) => <AttemptCard key={s.id} attempt={s} />)
        )}
      </section>
    </div>
  );
}
