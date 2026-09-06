"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, ExternalLink, Loader2, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { FormError } from "@/components/auth/form-error";
import { SubmissionStatusBadge } from "@/components/common/submission-status-badge";
import { WorkspaceCompletionPanel } from "@/components/industry/internship-program/workspace-completion-panel";
import { WorkspaceStipendPanel } from "@/components/industry/internship-program/workspace-stipend-panel";
import { ApiError } from "@/lib/api";
import {
  getProgramSubmission,
  listProgramSubmissions,
  reviewProgramSubmission,
  startProgramSubmissionReview,
} from "@/lib/industry/internship-program";
import {
  REVIEW_VERDICT_LABEL,
  type IndustrySubmission,
  type IndustrySubmissionDetail,
  type IndustrySubmissionListItem,
  type ReviewVerdict,
  type SubmissionReview,
} from "@/types/internship-program";

const SELECT_CLASS =
  "h-8 rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; submissions: IndustrySubmissionListItem[] };

function fmt(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleString();
}

function LinkRow({ label, url }: { label: string; url: string | null }) {
  if (!url) return null;
  return (
    <p className="flex items-center gap-1.5 text-sm">
      <span className="text-muted-foreground">{label}:</span>
      <a
        href={url}
        target="_blank"
        rel="noopener noreferrer"
        className="inline-flex items-center gap-1 break-all text-primary hover:underline"
      >
        {url} <ExternalLink className="size-3 shrink-0" />
      </a>
    </p>
  );
}

function ReviewLine({ review }: { review: SubmissionReview }) {
  return (
    <div className="rounded-md border border-primary/20 bg-primary/[0.03] px-2.5 py-1.5 text-sm">
      <div className="flex flex-wrap items-center gap-2">
        <SubmissionStatusBadge status={review.verdict} />
        {review.score != null && (
          <span className="text-xs text-muted-foreground">Score: {review.score}</span>
        )}
        <span className="text-xs text-muted-foreground">{fmt(review.created_at)}</span>
      </div>
      {review.feedback ? (
        <p className="mt-1 whitespace-pre-wrap text-muted-foreground">{review.feedback}</p>
      ) : null}
    </div>
  );
}

function AttemptCard({ attempt }: { attempt: IndustrySubmission }) {
  return (
    <div className="flex flex-col gap-1.5 rounded-md border px-3 py-2">
      <div className="flex flex-wrap items-center gap-2">
        <span className="text-sm font-medium">Attempt {attempt.attempt_number}</span>
        <SubmissionStatusBadge status={attempt.submission_status} />
        <span className="text-xs text-muted-foreground">{fmt(attempt.submitted_at)}</span>
      </div>
      <LinkRow label="Repo" url={attempt.repo_url} />
      <LinkRow label="Live URL" url={attempt.live_url} />
      <LinkRow label="Attachment" url={attempt.attachment_url} />
      {attempt.notes ? (
        <p className="text-sm whitespace-pre-wrap text-muted-foreground">{attempt.notes}</p>
      ) : null}
      {attempt.reviews.length > 0 && (
        <div className="mt-1 flex flex-col gap-1.5">
          {attempt.reviews.map((r) => (
            <ReviewLine key={r.id} review={r} />
          ))}
        </div>
      )}
    </div>
  );
}

const FEEDBACK_REQUIRED: ReviewVerdict[] = ["REVISION_REQUESTED", "REJECTED"];

function ReviewForm({
  verdict,
  maxScore,
  busy,
  onSubmit,
  onCancel,
}: {
  verdict: ReviewVerdict;
  maxScore: number | null;
  busy: boolean;
  onSubmit: (feedback: string, score: number | null) => void;
  onCancel: () => void;
}) {
  const [feedback, setFeedback] = useState("");
  const [score, setScore] = useState("");
  const feedbackRequired = FEEDBACK_REQUIRED.includes(verdict);
  const invalid =
    (feedbackRequired && !feedback.trim()) ||
    (score.trim() !== "" &&
      (Number.isNaN(Number(score)) ||
        Number(score) < 0 ||
        (maxScore != null && Number(score) > maxScore)));

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-dashed p-3">
      <p className="text-sm font-medium">{REVIEW_VERDICT_LABEL[verdict]}</p>
      <div className="space-y-1.5">
        <Label htmlFor="review-feedback">
          Feedback{feedbackRequired ? " (required)" : " (optional)"}
        </Label>
        <Textarea
          id="review-feedback"
          value={feedback}
          onChange={(e) => setFeedback(e.target.value)}
          rows={3}
          disabled={busy}
          placeholder={
            verdict === "REVISION_REQUESTED"
              ? "What should the intern change before resubmitting?"
              : "Notes for the intern"
          }
        />
      </div>
      {maxScore != null && (
        <div className="space-y-1.5">
          <Label htmlFor="review-score">Score (out of {maxScore})</Label>
          <Input
            id="review-score"
            type="number"
            min={0}
            max={maxScore}
            value={score}
            onChange={(e) => setScore(e.target.value)}
            disabled={busy}
          />
        </div>
      )}
      <div className="flex gap-2">
        <Button
          size="sm"
          onClick={() => onSubmit(feedback.trim(), score.trim() === "" ? null : Number(score))}
          disabled={busy || invalid}
        >
          {busy && <Loader2 className="size-3.5 animate-spin" />}
          Submit {REVIEW_VERDICT_LABEL[verdict].toLowerCase()}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>
          Cancel
        </Button>
      </div>
    </div>
  );
}

const ACTIONS_BY_STATUS: Record<string, (ReviewVerdict | "START")[]> = {
  SUBMITTED: ["START", "ACCEPTED", "REVISION_REQUESTED", "REJECTED"],
  UNDER_REVIEW: ["ACCEPTED", "REVISION_REQUESTED", "REJECTED"],
};

function SubmissionDetail({
  internshipId,
  submissionId,
  onReviewed,
  onBack,
}: {
  internshipId: string;
  submissionId: string;
  onReviewed: () => void;
  onBack: () => void;
}) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "error"; message: string }
    | { status: "ready"; detail: IndustrySubmissionDetail }
  >({ status: "loading" });
  const [pending, setPending] = useState<ReviewVerdict | null>(null);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getProgramSubmission(internshipId, submissionId)
      .then((detail) => {
        if (!cancelled) setState({ status: "ready", detail });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load this submission.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [internshipId, submissionId]);

  async function run(fn: () => Promise<IndustrySubmissionDetail>) {
    setBusy(true);
    setActionError(null);
    try {
      const detail = await fn();
      setState({ status: "ready", detail });
      setPending(null);
      onReviewed();
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Could not record that review. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="flex flex-col gap-4">
      <Button variant="ghost" size="sm" className="w-fit" onClick={onBack}>
        <ArrowLeft className="size-3.5" /> Back to all submissions
      </Button>
      {state.status === "loading" && (
        <p className="text-sm text-muted-foreground" aria-busy="true">
          Loading submission…
        </p>
      )}
      {state.status === "error" && <p className="text-sm text-destructive">{state.message}</p>}
      {state.status === "ready" &&
        (() => {
          const { detail } = state;
          const cur = detail.submission;
          const actions = ACTIONS_BY_STATUS[cur.submission_status] ?? [];
          return (
            <Card>
              <CardContent className="flex flex-col gap-4 py-4">
                <div>
                  <h2 className="text-lg font-semibold">
                    {detail.assignment_title ?? "Assignment"}
                  </h2>
                  <p className="text-sm text-muted-foreground">
                    {detail.module_title ? `${detail.module_title} · ` : ""}
                    {detail.student_name ?? "Intern"} · attempt {cur.attempt_number}
                  </p>
                  <div className="mt-1.5">
                    <SubmissionStatusBadge status={cur.submission_status} />
                  </div>
                </div>

                <FormError message={actionError} />

                {pending ? (
                  <ReviewForm
                    verdict={pending}
                    maxScore={detail.assignment_max_score}
                    busy={busy}
                    onCancel={() => setPending(null)}
                    onSubmit={(feedback, score) =>
                      void run(() =>
                        reviewProgramSubmission(internshipId, cur.id, {
                          verdict: pending,
                          feedback: feedback || null,
                          score,
                        }),
                      )
                    }
                  />
                ) : actions.length > 0 ? (
                  <div className="flex flex-wrap gap-2">
                    {actions.includes("START") && (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={busy}
                        onClick={() =>
                          void run(() =>
                            startProgramSubmissionReview(internshipId, cur.id),
                          )
                        }
                      >
                        {busy && <Loader2 className="size-3.5 animate-spin" />}
                        Start review
                      </Button>
                    )}
                    {(["ACCEPTED", "REVISION_REQUESTED", "REJECTED"] as ReviewVerdict[])
                      .filter((v) => actions.includes(v))
                      .map((v) => (
                        <Button
                          key={v}
                          size="sm"
                          variant={v === "ACCEPTED" ? "default" : "outline"}
                          disabled={busy}
                          onClick={() => {
                            setActionError(null);
                            setPending(v);
                          }}
                        >
                          {REVIEW_VERDICT_LABEL[v]}
                        </Button>
                      ))}
                  </div>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    This attempt has been reviewed. The intern must submit a new attempt to
                    continue.
                  </p>
                )}

                <div className="flex flex-col gap-2">
                  <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                    Attempt history
                  </p>
                  {detail.attempts.map((a) => (
                    <AttemptCard key={a.id} attempt={a} />
                  ))}
                </div>
              </CardContent>
            </Card>
          );
        })()}
    </div>
  );
}

/** Industry view of every submission for an internship's program, with
 * Phase 6 review controls (start review / accept / request revision /
 * reject). The backend state machine is authoritative -- the UI only
 * shows the actions the current status allows. */
export function ProgramSubmissionsView({ internshipId }: { internshipId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [assignmentFilter, setAssignmentFilter] = useState("");
  const [studentFilter, setStudentFilter] = useState("");

  const reload = useCallback(() => {
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { submissions } = await listProgramSubmissions(internshipId);
        if (!cancelled) setState({ status: "ready", submissions });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load submissions."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [internshipId, reloadKey]);

  const submissions = useMemo(
    () => (state.status === "ready" ? state.submissions : []),
    [state],
  );

  const assignmentOptions = useMemo(() => {
    const map = new Map<string, string>();
    for (const s of submissions) {
      if (!map.has(s.assignment_id)) {
        map.set(s.assignment_id, s.assignment_title ?? "Assignment");
      }
    }
    return [...map.entries()];
  }, [submissions]);

  const studentOptions = useMemo(() => {
    const set = new Set<string>();
    for (const s of submissions) if (s.student_name) set.add(s.student_name);
    return [...set];
  }, [submissions]);

  const workspaces = useMemo(() => {
    const map = new Map<string, string | null>();
    for (const s of submissions) {
      if (!map.has(s.workspace_id)) map.set(s.workspace_id, s.student_name);
    }
    return [...map.entries()];
  }, [submissions]);

  const filtered = submissions.filter(
    (s) =>
      (!assignmentFilter || s.assignment_id === assignmentFilter) &&
      (!studentFilter || s.student_name === studentFilter),
  );

  return (
    <div className="flex flex-col gap-5">
      <Link
        href={`/industry/internships/${internshipId}/program`}
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> Back to program
      </Link>
      <div>
        <h1 className="text-xl font-semibold">Submissions</h1>
        <p className="text-sm text-muted-foreground">
          Review every attempt interns have made against this program&apos;s assignments.
        </p>
      </div>

      {!selectedId && workspaces.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
            Completion
          </h2>
          <div className="flex flex-col gap-2">
            {workspaces.map(([workspaceId, studentName]) => (
              <WorkspaceCompletionPanel
                key={workspaceId}
                workspaceId={workspaceId}
                studentName={studentName}
              />
            ))}
          </div>
        </section>
      )}

      {!selectedId && workspaces.length > 0 && (
        <section className="flex flex-col gap-3">
          <h2 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
            Stipend
          </h2>
          <div className="flex flex-col gap-2">
            {workspaces.map(([workspaceId, studentName]) => (
              <WorkspaceStipendPanel
                key={workspaceId}
                workspaceId={workspaceId}
                studentName={studentName}
              />
            ))}
          </div>
        </section>
      )}

      {selectedId ? (
        <SubmissionDetail
          key={selectedId}
          internshipId={internshipId}
          submissionId={selectedId}
          onReviewed={reload}
          onBack={() => setSelectedId(null)}
        />
      ) : state.status === "loading" ? (
        <p className="text-sm text-muted-foreground" aria-busy="true" aria-label="Loading submissions">
          Loading submissions…
        </p>
      ) : state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" />
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
            <Button variant="outline" size="sm" onClick={reload}>
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          </CardContent>
        </Card>
      ) : submissions.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No submissions yet.
          </CardContent>
        </Card>
      ) : (
        <>
          <div className="flex flex-wrap gap-3">
            <label className="flex items-center gap-2 text-sm">
              <span className="text-muted-foreground">Assignment</span>
              <select
                className={SELECT_CLASS}
                value={assignmentFilter}
                onChange={(e) => setAssignmentFilter(e.target.value)}
                aria-label="Filter by assignment"
              >
                <option value="">All</option>
                {assignmentOptions.map(([id, label]) => (
                  <option key={id} value={id}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
            {studentOptions.length > 0 && (
              <label className="flex items-center gap-2 text-sm">
                <span className="text-muted-foreground">Intern</span>
                <select
                  className={SELECT_CLASS}
                  value={studentFilter}
                  onChange={(e) => setStudentFilter(e.target.value)}
                  aria-label="Filter by intern"
                >
                  <option value="">All</option>
                  {studentOptions.map((name) => (
                    <option key={name} value={name}>
                      {name}
                    </option>
                  ))}
                </select>
              </label>
            )}
          </div>

          <div className="flex flex-col gap-2">
            {filtered.map((s) => (
              <Card key={s.id}>
                <CardContent className="flex flex-wrap items-center gap-x-3 gap-y-1.5 py-3">
                  <div className="min-w-0 flex-1">
                    <p className="truncate font-medium">{s.assignment_title ?? "Assignment"}</p>
                    <p className="text-xs text-muted-foreground">
                      {s.module_title ? `${s.module_title} · ` : ""}
                      {s.student_name ?? "Intern"} · attempt {s.attempt_number} of{" "}
                      {s.attempt_count} · {fmt(s.submitted_at)}
                    </p>
                  </div>
                  <SubmissionStatusBadge status={s.submission_status} />
                  <Button size="sm" variant="outline" onClick={() => setSelectedId(s.id)}>
                    Review
                  </Button>
                </CardContent>
              </Card>
            ))}
            {filtered.length === 0 && (
              <p className="text-sm text-muted-foreground">
                No submissions match the current filters.
              </p>
            )}
          </div>
        </>
      )}
    </div>
  );
}
