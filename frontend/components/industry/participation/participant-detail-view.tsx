"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Building2, GraduationCap } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Textarea } from "@/components/ui/textarea";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { getSkillCatalog, type CatalogSkill } from "@/lib/industry/skills";
import {
  completeWorkspace,
  createFeedback,
  createRecommendation,
  createReview,
  finalizeEvaluation,
  getCompletion,
  getCriteria,
  getEvaluation,
  getFeedback,
  getRecommendations,
  getSubmissions,
  getWorkspace,
  saveEvaluation,
} from "@/lib/industry/participation";
import {
  FEEDBACK_TYPE_LABELS,
  FEEDBACK_TYPES,
  RECOMMENDATION_PRIORITIES,
  RECOMMENDED_LEVELS,
  REVIEW_STATUS_LABELS,
  REVIEW_STATUSES,
  type CompletionResponse,
  type CriterionResponse,
  type EvaluationResponse,
  type FeedbackResponse,
  type FeedbackType,
  type RecommendationPriority,
  type SkillRecommendationResponse,
  type SubmissionResponse,
  type WorkspaceResponse,
} from "@/types/participation";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; workspace: WorkspaceResponse };

export function ParticipantDetailView({ workspaceId }: { workspaceId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [tab, setTab] = useState("submissions");

  useEffect(() => {
    let cancelled = false;
    getWorkspace(workspaceId)
      .then((workspace) => !cancelled && setState({ status: "ready", workspace }))
      .catch((err) => {
        if (!cancelled)
          setState({ status: "error", error: err instanceof ApiError ? err : new ApiError(0, "Could not load this participant.") });
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId, reloadKey]);

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
  const name = workspace.student_name ?? `Applicant ${workspace.student_id.slice(0, 8)}`;

  return (
    <div className="space-y-4">
      <Link href="#" onClick={(e) => { e.preventDefault(); history.back(); }} className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground">
        <ArrowLeft className="size-3.5" /> Back
      </Link>

      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h1 className="text-xl font-semibold">{name}</h1>
          <p className="flex items-center gap-1 text-sm text-muted-foreground">
            <Building2 className="size-3.5" aria-hidden="true" /> {workspace.opportunity?.title}
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
          <TabsTrigger value="submissions">Submissions</TabsTrigger>
          <TabsTrigger value="feedback">Feedback</TabsTrigger>
          <TabsTrigger value="recommendations">Skill Recommendations</TabsTrigger>
          <TabsTrigger value="evaluation">Final Evaluation</TabsTrigger>
        </TabsList>

        <TabsContent value="submissions" className="pt-4">
          <SubmissionsPanel workspaceId={workspaceId} />
        </TabsContent>
        <TabsContent value="feedback" className="pt-4">
          <FeedbackPanel workspaceId={workspaceId} studentId={workspace.student_id} />
        </TabsContent>
        <TabsContent value="recommendations" className="pt-4">
          <RecommendationsPanel workspaceId={workspaceId} />
        </TabsContent>
        <TabsContent value="evaluation" className="pt-4">
          <EvaluationPanel workspace={workspace} onReload={() => setReloadKey((k) => k + 1)} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function SubmissionsPanel({ workspaceId }: { workspaceId: string }) {
  const [submissions, setSubmissions] = useState<SubmissionResponse[] | null>(null);
  const [reloadKey, setReloadKey] = useState(0);
  const [reviewing, setReviewing] = useState<string | null>(null);
  const [score, setScore] = useState("");
  const [feedback, setFeedback] = useState("");
  const [verdict, setVerdict] = useState<(typeof REVIEW_STATUSES)[number]>("ACCEPTED");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getSubmissions(workspaceId).then((r) => setSubmissions(r.submissions));
  }, [workspaceId, reloadKey]);

  async function submitReview(submissionId: string) {
    setError(null);
    try {
      await createReview(submissionId, { score: score ? Number(score) : null, feedback: feedback || null, status: verdict });
      setReviewing(null);
      setScore("");
      setFeedback("");
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not record the review.");
    }
  }

  if (submissions === null) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (submissions.length === 0) {
    return <EmptyState title="No submissions yet" description="The student hasn't submitted any work yet." />;
  }

  return (
    <div className="space-y-3">
      <FormError message={error} />
      {submissions.map((s) => (
        <Card key={s.id}>
          <CardContent className="space-y-2 py-4">
            <div className="flex items-start justify-between gap-2">
              <div>
                <p className="font-medium">{s.assignment_title ?? "Assignment"}</p>
                <p className="text-xs text-muted-foreground">Attempt #{s.attempt_number}</p>
              </div>
              <Badge variant="ghost">{s.status}</Badge>
            </div>
            {s.submission_text && <p className="text-sm whitespace-pre-line">{s.submission_text}</p>}
            {s.submission_url && (
              <a href={s.submission_url} target="_blank" rel="noreferrer" className="text-sm text-indigo-600 hover:underline dark:text-indigo-400">
                {s.submission_url}
              </a>
            )}
            {s.latest_review ? (
              <div className="rounded-md bg-muted/50 p-2 text-xs">
                <Badge variant="ghost" className="mb-1">
                  {REVIEW_STATUS_LABELS[s.latest_review.status]}
                </Badge>
                {s.latest_review.score != null ? <p>Score: {s.latest_review.score}</p> : null}
                {s.latest_review.feedback ? <p>{s.latest_review.feedback}</p> : null}
              </div>
            ) : reviewing === s.id ? (
              <div className="space-y-2 rounded-md border p-2">
                <div className="flex flex-wrap gap-2">
                  <Select value={verdict} onValueChange={(v) => setVerdict(v as (typeof REVIEW_STATUSES)[number])}>
                    <SelectTrigger className="w-40">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {REVIEW_STATUSES.map((v) => (
                        <SelectItem key={v} value={v}>
                          {REVIEW_STATUS_LABELS[v]}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <Input placeholder="Score (optional)" type="number" value={score} onChange={(e) => setScore(e.target.value)} className="w-32" />
                </div>
                <Textarea placeholder="Feedback" value={feedback} onChange={(e) => setFeedback(e.target.value)} rows={2} />
                <div className="flex gap-2">
                  <Button size="sm" onClick={() => submitReview(s.id)}>
                    Save Review
                  </Button>
                  <Button size="sm" variant="ghost" onClick={() => setReviewing(null)}>
                    Cancel
                  </Button>
                </div>
              </div>
            ) : (
              <Button size="sm" variant="outline" onClick={() => setReviewing(s.id)}>
                Review
              </Button>
            )}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}

function FeedbackPanel({ workspaceId }: { workspaceId: string; studentId: string }) {
  const [items, setItems] = useState<FeedbackResponse[] | null>(null);
  const [type, setType] = useState<FeedbackType>("GENERAL");
  const [text, setText] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    getFeedback(workspaceId).then((r) => setItems(r.feedback));
  }, [workspaceId, reloadKey]);

  async function add() {
    if (!text.trim()) return;
    await createFeedback(workspaceId, { feedback_type: type, feedback: text });
    setText("");
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Select value={type} onValueChange={(v) => setType(v as FeedbackType)}>
          <SelectTrigger className="w-40">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {FEEDBACK_TYPES.map((t) => (
              <SelectItem key={t} value={t}>
                {FEEDBACK_TYPE_LABELS[t]}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Textarea placeholder="Feedback for this student…" value={text} onChange={(e) => setText(e.target.value)} rows={2} className="flex-1" />
      </div>
      <Button size="sm" onClick={add} disabled={!text.trim()}>
        Add Feedback
      </Button>
      {items === null ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <EmptyState title="No feedback yet" description="Leave general observations about this student's performance." />
      ) : (
        <div className="space-y-2">
          {items.map((f) => (
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
  );
}

function RecommendationsPanel({ workspaceId }: { workspaceId: string }) {
  const [items, setItems] = useState<SkillRecommendationResponse[] | null>(null);
  const [skills, setSkills] = useState<CatalogSkill[]>([]);
  const [skillId, setSkillId] = useState("");
  const [reason, setReason] = useState("");
  const [priority, setPriority] = useState<RecommendationPriority>("MEDIUM");
  const [level, setLevel] = useState<(typeof RECOMMENDED_LEVELS)[number] | "">("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    getRecommendations(workspaceId).then((r) => setItems(r.recommendations));
  }, [workspaceId, reloadKey]);

  useEffect(() => {
    getSkillCatalog().then((r) => setSkills(r.skills));
  }, []);

  async function add() {
    if (!skillId || !reason.trim()) return;
    await createRecommendation(workspaceId, { skill_id: skillId, reason, priority, recommended_level: level || null });
    setReason("");
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Select value={skillId} onValueChange={(v) => setSkillId(v ?? "")}>
          <SelectTrigger className="w-48">
            <SelectValue placeholder="Skill" />
          </SelectTrigger>
          <SelectContent>
            {skills.map((s) => (
              <SelectItem key={s.id} value={s.id}>
                {s.name}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={level} onValueChange={(v) => setLevel((v as (typeof RECOMMENDED_LEVELS)[number]) ?? "")}>
          <SelectTrigger className="w-36">
            <SelectValue placeholder="Target level" />
          </SelectTrigger>
          <SelectContent>
            {RECOMMENDED_LEVELS.map((l) => (
              <SelectItem key={l} value={l}>
                {l}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Select value={priority} onValueChange={(v) => setPriority(v as RecommendationPriority)}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {RECOMMENDATION_PRIORITIES.map((p) => (
              <SelectItem key={p} value={p}>
                {p}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
      </div>
      <Textarea placeholder="Reason / advice for this student…" value={reason} onChange={(e) => setReason(e.target.value)} rows={2} />
      <Button size="sm" onClick={add} disabled={!skillId || !reason.trim()}>
        Add Recommendation
      </Button>
      {items === null ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : items.length === 0 ? (
        <EmptyState icon={GraduationCap} title="No recommendations yet" description="Suggest skills this student should strengthen." />
      ) : (
        <div className="space-y-2">
          {items.map((r) => (
            <Card key={r.id}>
              <CardContent className="space-y-1 py-3">
                <div className="flex items-center gap-2">
                  <p className="font-medium">{r.skill_name ?? "Skill"}</p>
                  <Badge variant="ghost">{r.priority}</Badge>
                  {r.recommended_level ? <Badge variant="secondary">{r.recommended_level}</Badge> : null}
                </div>
                <p className="text-sm whitespace-pre-line">{r.reason}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function EvaluationPanel({ workspace, onReload }: { workspace: WorkspaceResponse; onReload: () => void }) {
  const [criteria, setCriteria] = useState<CriterionResponse[] | null>(null);
  const [evaluation, setEvaluation] = useState<EvaluationResponse | null>(null);
  const [completion, setCompletion] = useState<CompletionResponse | null>(null);
  const [scores, setScores] = useState<Record<string, { score: string; feedback: string }>>({});
  const [overallFeedback, setOverallFeedback] = useState("");
  const [confirmFinalize, setConfirmFinalize] = useState(false);
  const [confirmComplete, setConfirmComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const programId = workspace.program_id;

  useEffect(() => {
    if (programId) getCriteria(programId).then((r) => setCriteria(r.criteria));
    getEvaluation(workspace.id).then((e) => {
      setEvaluation(e);
      setOverallFeedback(e.overall_feedback ?? "");
      const seeded: Record<string, { score: string; feedback: string }> = {};
      for (const s of e.scores) seeded[s.criterion_id] = { score: String(s.score), feedback: s.feedback ?? "" };
      setScores(seeded);
    });
    getCompletion(workspace.id)
      .then(setCompletion)
      .catch(() => setCompletion(null));
  }, [programId, workspace.id, reloadKey]);

  async function save() {
    setError(null);
    try {
      const payload = Object.entries(scores)
        .filter(([, v]) => v.score !== "")
        .map(([criterion_id, v]) => ({ criterion_id, score: Number(v.score), feedback: v.feedback || null }));
      await saveEvaluation(workspace.id, { overall_feedback: overallFeedback || null, scores: payload });
      setSuccess("Saved.");
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save.");
    }
  }

  async function finalize() {
    setConfirmFinalize(false);
    setError(null);
    try {
      await finalizeEvaluation(workspace.id);
      setSuccess("Evaluation finalized.");
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not finalize.");
    }
  }

  async function complete() {
    setConfirmComplete(false);
    setError(null);
    try {
      await completeWorkspace(workspace.id);
      setSuccess("Participation completed.");
      onReload();
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not complete this participation.");
    }
  }

  const isFinalized = evaluation?.status === "FINALIZED";

  return (
    <div className="space-y-3">
      <FormError message={error} />
      <FormSuccess message={success} />

      {completion ? (
        <Card>
          <CardContent className="py-4">
            <Badge variant="default">Completed</Badge>
            {completion.final_score != null ? <p className="mt-1 text-sm">Final score: {completion.final_score}%</p> : null}
          </CardContent>
        </Card>
      ) : null}

      {criteria === null || criteria.length === 0 ? null : (
        <div className="space-y-2">
          {criteria.map((c) => (
            <Card key={c.id}>
              <CardHeader>
                <CardTitle className="text-sm">
                  {c.name} <span className="text-xs font-normal text-muted-foreground">(max {c.max_score}, weight {c.weight}%)</span>
                </CardTitle>
              </CardHeader>
              <CardContent className="flex flex-col gap-2 sm:flex-row">
                <Input
                  type="number"
                  placeholder={`Score / ${c.max_score}`}
                  value={scores[c.id]?.score ?? ""}
                  disabled={isFinalized}
                  onChange={(e) => setScores((s) => ({ ...s, [c.id]: { ...s[c.id], score: e.target.value, feedback: s[c.id]?.feedback ?? "" } }))}
                  className="sm:w-32"
                />
                <Textarea
                  placeholder="Feedback for this criterion"
                  rows={1}
                  disabled={isFinalized}
                  value={scores[c.id]?.feedback ?? ""}
                  onChange={(e) => setScores((s) => ({ ...s, [c.id]: { score: s[c.id]?.score ?? "", feedback: e.target.value } }))}
                  className="flex-1"
                />
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <Textarea
        placeholder="Overall feedback"
        value={overallFeedback}
        disabled={isFinalized}
        onChange={(e) => setOverallFeedback(e.target.value)}
        rows={3}
      />

      {evaluation?.overall_score != null ? (
        <p className="text-sm font-medium">Overall Score: {evaluation.overall_score}%</p>
      ) : null}

      <div className="flex flex-wrap gap-2">
        {!isFinalized && (criteria?.length ?? 0) > 0 ? (
          <>
            <Button size="sm" variant="outline" onClick={save}>
              Save Draft
            </Button>
            <Button size="sm" onClick={() => setConfirmFinalize(true)}>
              Finalize Evaluation
            </Button>
          </>
        ) : null}
        {!completion ? (
          <Button size="sm" variant="outline" onClick={() => setConfirmComplete(true)}>
            Mark Participation Completed
          </Button>
        ) : null}
      </div>

      <ConfirmationDialog
        open={confirmFinalize}
        onOpenChange={setConfirmFinalize}
        title="Finalize this evaluation?"
        description="Once finalized, scores and feedback can no longer be changed."
        confirmLabel="Finalize"
        loading={false}
        onConfirm={finalize}
      />
      <ConfirmationDialog
        open={confirmComplete}
        onOpenChange={setConfirmComplete}
        title="Mark this participation as completed?"
        confirmLabel="Complete"
        loading={false}
        onConfirm={complete}
      />
    </div>
  );
}
