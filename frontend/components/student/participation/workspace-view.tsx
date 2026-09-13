"use client";

import { useEffect, useRef, useState } from "react";
import { AlertCircle, Building2, CheckCircle2, FileText, GraduationCap, Layers } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import {
  canSubmitAssignment,
  getAssignments,
  getCompletion,
  getEvaluation,
  getFeedback,
  getModules,
  getRecommendations,
  getResources,
  getSubmissions,
  getWorkspace,
  submitWork,
} from "@/lib/student/participation";
import {
  FEEDBACK_TYPE_LABELS,
  REVIEW_STATUS_LABELS,
  SUBMISSION_STATUS_LABELS,
  type AssignmentResponse,
  type CompletionResponse,
  type EvaluationResponse,
  type FeedbackResponse,
  type ModuleResponse,
  type ResourceResponse,
  type SkillRecommendationResponse,
  type SubmissionResponse,
  type WorkspaceResponse,
  type WorkspaceStatus,
} from "@/types/participation";
import { cn } from "@/lib/utils";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; workspace: WorkspaceResponse };

/** Small, informational-only tab attention counts -- built from the same
 * three already-existing aggregate endpoints the Assignments/Feedback
 * panels themselves call, fetched once here (best-effort, never blocking
 * the workspace itself) purely so the tab triggers can show a count
 * before the student has opened them. No read/unread persistence, no
 * per-item requests. */
interface TabBadgeCounts {
  needsRevisionCount: number;
  feedbackCount: number;
  recommendationsCount: number;
}

/** Shared Student Participation Workspace view -- Project/Training/
 * Workshop, all driven by the same API. Read-only for everything except
 * submitting work: no Industry editing controls are ever rendered here. */
export function StudentWorkspaceView({ workspaceId }: { workspaceId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [tab, setTab] = useState("overview");
  const [badgeCounts, setBadgeCounts] = useState<TabBadgeCounts | null>(null);
  // Only ever auto-picks the tab ONCE, right when this workspace's data
  // first arrives -- never again afterward, so a student who manually
  // switches tabs is never yanked back to Final Result.
  const tabAutoSelected = useRef(false);

  useEffect(() => {
    let cancelled = false;
    tabAutoSelected.current = false;
    getWorkspace(workspaceId)
      .then((workspace) => {
        if (cancelled) return;
        setState({ status: "ready", workspace });
        if (!tabAutoSelected.current) {
          tabAutoSelected.current = true;
          if (workspace.workspace_status === "COMPLETED") setTab("evaluation");
        }
      })
      .catch((err) => {
        if (!cancelled)
          setState({ status: "error", error: err instanceof ApiError ? err : new ApiError(0, "Could not load your workspace.") });
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getSubmissions(workspaceId)
        .then((r) => r.submissions.filter((s) => s.latest_review?.status === "NEEDS_REVISION").length)
        .catch(() => 0),
      getFeedback(workspaceId)
        .then((r) => r.feedback.length)
        .catch(() => 0),
      getRecommendations(workspaceId)
        .then((r) => r.recommendations.length)
        .catch(() => 0),
    ]).then(([needsRevisionCount, feedbackCount, recommendationsCount]) => {
      if (!cancelled) setBadgeCounts({ needsRevisionCount, feedbackCount, recommendationsCount });
    });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
          Loading…
        </CardContent>
      </Card>
    );
  }
  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">{state.error.message}</p>
        </CardContent>
      </Card>
    );
  }

  const { workspace } = state;

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">{workspace.opportunity?.title}</h1>
          <p className="flex items-center gap-1 text-sm text-muted-foreground">
            <Building2 className="size-3.5" aria-hidden="true" /> Your workspace
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant={workspace.workspace_status === "COMPLETED" ? "default" : "ghost"}>{workspace.workspace_status}</Badge>
          {workspace.progress ? (
            <Badge variant="secondary">
              {workspace.progress.completed_required}/{workspace.progress.published_required} required · {workspace.progress.percent}%
            </Badge>
          ) : null}
        </div>
      </div>

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="overview">Modules &amp; Resources</TabsTrigger>
          <TabsTrigger value="assignments">
            Assignments
            <TabCountBadge count={badgeCounts?.needsRevisionCount} tone="warning" />
          </TabsTrigger>
          <TabsTrigger value="feedback">
            Feedback
            <TabCountBadge count={badgeCounts ? badgeCounts.feedbackCount + badgeCounts.recommendationsCount : undefined} />
          </TabsTrigger>
          <TabsTrigger value="evaluation">Final Result</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="pt-4">
          <OverviewPanel workspaceId={workspaceId} />
        </TabsContent>
        <TabsContent value="assignments" className="pt-4">
          <AssignmentsPanel workspaceId={workspaceId} />
        </TabsContent>
        <TabsContent value="feedback" className="pt-4">
          <FeedbackAndRecommendationsPanel workspaceId={workspaceId} />
        </TabsContent>
        <TabsContent value="evaluation" className="pt-4">
          <EvaluationPanel workspaceId={workspaceId} workspaceStatus={workspace.workspace_status} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

/** Informational-only count badge for a tab trigger -- no read/unread
 * tracking, just "how many of these exist right now". Renders nothing
 * while the counts haven't loaded yet, or once loaded, when the count is
 * zero -- so a tab with nothing notable looks exactly as it did before
 * this phase. */
function TabCountBadge({ count, tone = "default" }: { count: number | undefined; tone?: "default" | "warning" }) {
  if (!count) return null;
  return (
    <Badge
      variant="outline"
      className={cn(
        "ml-1 h-4 min-w-4 justify-center rounded-full px-1 text-[10px] leading-none",
        tone === "warning"
          ? "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400"
          : "border-indigo-500/30 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
      )}
    >
      {count}
    </Badge>
  );
}

function OverviewPanel({ workspaceId }: { workspaceId: string }) {
  const [modules, setModules] = useState<ModuleResponse[] | null>(null);
  const [resources, setResources] = useState<ResourceResponse[] | null>(null);

  useEffect(() => {
    getModules(workspaceId).then((r) => setModules(r.modules));
    getResources(workspaceId).then((r) => setResources(r.resources));
  }, [workspaceId]);

  return (
    <div className="space-y-4">
      <div>
        <h3 className="mb-2 text-sm font-semibold text-muted-foreground uppercase">Modules</h3>
        {modules === null ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : modules.length === 0 ? (
          <EmptyState icon={Layers} title="No modules yet" description="Your Industry contact hasn't published any modules yet." />
        ) : (
          <div className="space-y-2">
            {modules.map((m) => (
              <Card key={m.id}>
                <CardContent className="py-3">
                  <p className="font-medium">{m.title}</p>
                  {m.description ? <p className="text-sm text-muted-foreground">{m.description}</p> : null}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
      <div>
        <h3 className="mb-2 text-sm font-semibold text-muted-foreground uppercase">Resources</h3>
        {resources === null ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : resources.length === 0 ? (
          <EmptyState icon={FileText} title="No resources yet" description="Videos, documents, and links will show up here." />
        ) : (
          <div className="space-y-2">
            {resources.map((r) => (
              <Card key={r.id}>
                <CardContent className="py-3">
                  <p className="font-medium">{r.title}</p>
                  {r.resource_url ? (
                    <a href={r.resource_url} target="_blank" rel="noreferrer" className="text-sm text-indigo-600 hover:underline dark:text-indigo-400">
                      {r.resource_url}
                    </a>
                  ) : null}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function AssignmentsPanel({ workspaceId }: { workspaceId: string }) {
  const [assignments, setAssignments] = useState<AssignmentResponse[] | null>(null);
  const [submissions, setSubmissions] = useState<SubmissionResponse[] | null>(null);
  const [submittingFor, setSubmittingFor] = useState<string | null>(null);
  const [text, setText] = useState("");
  const [url, setUrl] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    getAssignments(workspaceId).then((r) => setAssignments(r.assignments));
    getSubmissions(workspaceId).then((r) => setSubmissions(r.submissions));
  }, [workspaceId, reloadKey]);

  async function submit(assignmentId: string) {
    setError(null);
    try {
      await submitWork(workspaceId, { assignment_id: assignmentId, submission_text: text || null, submission_url: url || null });
      setSuccess("Submitted.");
      setSubmittingFor(null);
      setText("");
      setUrl("");
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit your work.");
    }
  }

  if (assignments === null) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (assignments.length === 0) {
    return <EmptyState title="No assignments yet" description="No assignments have been published yet." />;
  }

  return (
    <div className="space-y-3">
      <FormError message={error} />
      <FormSuccess message={success} />
      {assignments.map((a) => {
        const mySubmissions = (submissions ?? []).filter((s) => s.assignment_id === a.id);
        const latest = mySubmissions[0];
        return (
          <Card key={a.id}>
            <CardContent className="space-y-2 py-4">
              <div className="flex items-start justify-between gap-2">
                <div>
                  <p className="font-medium">{a.title}</p>
                  {a.description ? <p className="text-sm text-muted-foreground">{a.description}</p> : null}
                  {a.due_at ? <p className="text-xs text-muted-foreground">Due {new Date(a.due_at).toLocaleDateString()}</p> : null}
                </div>
                <Badge variant={a.is_required ? "default" : "ghost"}>{a.is_required ? "Required" : "Optional"}</Badge>
              </div>

              {mySubmissions.length > 0 ? (
                <div className="space-y-1.5">
                  {mySubmissions.map((s) => (
                    <SubmissionStatusRow key={s.id} submission={s} />
                  ))}
                </div>
              ) : (
                <Badge variant="outline" className="text-muted-foreground">
                  Not Submitted
                </Badge>
              )}

              {submittingFor === a.id ? (
                <div className="space-y-2 rounded-md border p-2">
                  <Textarea placeholder="Submission text (optional)" value={text} onChange={(e) => setText(e.target.value)} rows={3} />
                  <Input placeholder="Submission URL (optional)" value={url} onChange={(e) => setUrl(e.target.value)} />
                  <div className="flex gap-2">
                    <Button size="sm" onClick={() => submit(a.id)} disabled={!text.trim() && !url.trim()}>
                      Submit
                    </Button>
                    <Button size="sm" variant="ghost" onClick={() => setSubmittingFor(null)}>
                      Cancel
                    </Button>
                  </div>
                </div>
              ) : canSubmitAssignment(latest) ? (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={() => {
                    setSubmittingFor(a.id);
                    setText("");
                    setUrl("");
                  }}
                >
                  {mySubmissions.length > 0 ? "Resubmit Work" : "Submit Work"}
                </Button>
              ) : (
                <p className="text-xs text-muted-foreground">{assignmentActionHint(latest)}</p>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

/** One past submission's status, made visually obvious: the industry
 * review's own status (ACCEPTED/NEEDS_REVISION/REVIEWED) when a review
 * exists, otherwise the submission's own pipeline status (Submitted/Under
 * Review). NEEDS_REVISION gets distinct warning styling and its feedback
 * text called out explicitly, since that is the one state a student most
 * needs to notice. This only changes what is DISPLAYED -- it does not
 * change whether the Resubmit button above is enabled. */
/** The reason no Submit/Resubmit action is offered right now, for a
 * submission canSubmitAssignment() has already said is not eligible. Only
 * called in that branch, so `latest` is always defined here (an assignment
 * with NO submission is always eligible). */
function assignmentActionHint(latest: SubmissionResponse | undefined): string {
  const review = latest?.latest_review;
  if (!review) return "Waiting for Industry to review your submission.";
  if (review.status === "ACCEPTED") return "Accepted — no further submission needed.";
  return "Reviewed by Industry — no further submission needed.";
}

function SubmissionStatusRow({ submission }: { submission: SubmissionResponse }) {
  const review = submission.latest_review;
  const needsRevision = review?.status === "NEEDS_REVISION";
  return (
    <div
      className={cn(
        "rounded-md p-2 text-xs",
        needsRevision ? "border border-amber-500/30 bg-amber-500/5" : "bg-muted/50",
      )}
    >
      <div className="flex items-center justify-between gap-2">
        <p className="font-medium text-foreground">Attempt #{submission.attempt_number}</p>
        {review ? (
          <Badge
            variant="outline"
            className={
              review.status === "ACCEPTED"
                ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                : needsRevision
                  ? "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400"
                  : undefined
            }
          >
            {REVIEW_STATUS_LABELS[review.status]}
          </Badge>
        ) : (
          <Badge variant="outline">{SUBMISSION_STATUS_LABELS[submission.status]}</Badge>
        )}
      </div>
      {review?.score != null && <p className="mt-1 text-muted-foreground">Score: {review.score}</p>}
      {review?.feedback && (
        <p className="mt-1 text-foreground">
          {needsRevision ? "Industry requested changes: " : "Feedback: "}
          {review.feedback}
        </p>
      )}
    </div>
  );
}

function FeedbackAndRecommendationsPanel({ workspaceId }: { workspaceId: string }) {
  const [feedback, setFeedback] = useState<FeedbackResponse[] | null>(null);
  const [recommendations, setRecommendations] = useState<SkillRecommendationResponse[] | null>(null);

  useEffect(() => {
    getFeedback(workspaceId).then((r) => setFeedback(r.feedback));
    getRecommendations(workspaceId).then((r) => setRecommendations(r.recommendations));
  }, [workspaceId]);

  return (
    <div className="space-y-4">
      <div>
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-muted-foreground uppercase">
          Feedback
          {feedback && feedback.length > 0 ? (
            <span className="text-xs font-normal normal-case text-muted-foreground">({feedback.length})</span>
          ) : null}
        </h3>
        {feedback === null ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : feedback.length === 0 ? (
          <EmptyState title="No feedback yet" description="Industry feedback will appear here after your work is reviewed." />
        ) : (
          <div className="space-y-2">
            {feedback.map((f) => (
              <Card key={f.id}>
                <CardContent className="space-y-1 py-3">
                  <Badge variant="ghost">{FEEDBACK_TYPE_LABELS[f.feedback_type]}</Badge>
                  {f.title ? <p className="font-medium">{f.title}</p> : null}
                  <p className="text-sm whitespace-pre-line">{f.feedback}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
      <div>
        <h3 className="mb-2 flex items-center gap-1.5 text-sm font-semibold text-muted-foreground uppercase">
          Skill Recommendations
          {recommendations && recommendations.length > 0 ? (
            <span className="text-xs font-normal normal-case text-muted-foreground">({recommendations.length})</span>
          ) : null}
        </h3>
        {recommendations === null ? (
          <p className="text-sm text-muted-foreground">Loading…</p>
        ) : recommendations.length === 0 ? (
          <EmptyState icon={GraduationCap} title="No skill recommendations yet" description="Skills Industry suggests you strengthen will appear here." />
        ) : (
          <div className="space-y-2">
            {recommendations.map((r) => (
              <Card key={r.id}>
                <CardContent className="space-y-1 py-3">
                  <div className="flex items-center gap-2">
                    <p className="font-medium">{r.skill_name ?? "Skill"}</p>
                    <Badge variant="ghost">{r.priority}</Badge>
                  </div>
                  <p className="text-sm whitespace-pre-line">{r.reason}</p>
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}

function EvaluationPanel({
  workspaceId,
  workspaceStatus,
}: {
  workspaceId: string;
  workspaceStatus: WorkspaceStatus;
}) {
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [completion, setCompletion] = useState<CompletionResponse | null>(null);

  useEffect(() => {
    getEvaluation(workspaceId)
      .then(setEvaluation)
      .catch(() => setEvaluation(null));
    getCompletion(workspaceId)
      .then(setCompletion)
      .catch(() => setCompletion(null));
  }, [workspaceId]);

  if (!evaluation && !completion) {
    // A COMPLETED workspace with neither record yet is an honest, rare
    // data-timing edge case (never fabricated) -- everything else
    // (Workshop with no formal rubric, an ACTIVE workspace not yet
    // evaluated) is exactly the same "nothing here yet" state as before.
    return (
      <EmptyState
        title="Not evaluated yet"
        description={
          workspaceStatus === "COMPLETED"
            ? "This workspace is marked complete, but result details aren't available yet."
            : "Your final evaluation will appear here once Industry finalizes it."
        }
      />
    );
  }

  return (
    <div className="space-y-3">
      {completion ? (
        <Card className="border-emerald-500/30 bg-emerald-500/5">
          <CardContent className="flex flex-col gap-1 py-4">
            <div className="flex items-center gap-2">
              <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
              <span className="font-medium text-emerald-700 dark:text-emerald-400">Workspace Completed</span>
            </div>
            {completion.completed_at ? (
              <p className="text-sm text-muted-foreground">
                Completed on {new Date(completion.completed_at).toLocaleDateString()}
              </p>
            ) : null}
            {completion.final_score != null ? (
              <p className="text-sm font-medium">Final score: {completion.final_score}%</p>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {evaluation ? (
        <>
          {/* No rubric/criteria for this program (e.g. a lightweight
           * Workshop) is a normal, valid shape -- evaluation.scores is
           * simply empty, and nothing renders here beyond the overall
           * score/feedback below, if those exist. Never a "no criteria
           * defined" message. */}
          {evaluation.scores.map((s) => (
            <Card key={s.id}>
              <CardContent className="flex items-center justify-between py-3">
                <p className="font-medium">{s.criterion_name}</p>
                <p className="text-sm">
                  {s.score} / {s.max_score}
                </p>
              </CardContent>
              {s.feedback ? <CardContent className="pt-0 text-sm text-muted-foreground">{s.feedback}</CardContent> : null}
            </Card>
          ))}
          {evaluation.overall_score != null ? <p className="font-medium">Overall Score: {evaluation.overall_score}%</p> : null}
          {evaluation.overall_feedback ? <p className="text-sm whitespace-pre-line">{evaluation.overall_feedback}</p> : null}
        </>
      ) : null}
    </div>
  );
}
