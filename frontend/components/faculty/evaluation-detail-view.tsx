"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { EvaluationStatusBadge } from "@/components/faculty/evaluation-status-badge";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";
import { getEvaluation, listCandidateRubrics, saveEvaluation, updateEvaluationStatus } from "@/lib/faculty/evaluations";
import type { EvaluationDetail, Rubric } from "@/types/evaluation";

/**
 * Phase 2: one assigned evaluation, following the actual existing
 * backend lifecycle (ASSIGNED -> IN_PROGRESS -> SUBMITTED -> FINALIZED,
 * 045_evaluation_foundation.sql) -- never a parallel state machine.
 * Every transition/save call goes straight through
 * app.services.evaluation_service's existing, already-tested functions;
 * this component computes and sends nothing the backend doesn't accept
 * as-is, and never writes evaluation_status/final_score/final_percentage
 * itself -- those remain entirely fold_in_attempt_evaluation()'s job.
 *
 * Content (rubric_id/awarded_marks/feedback) is editable in both
 * IN_PROGRESS and SUBMITTED -- the backend's own immutability trigger
 * (prevent_unauthorized_evaluation_change) only locks FINALIZED, never
 * SUBMITTED, so this intentionally does not invent a stricter
 * "submitted = locked" rule the backend doesn't have.
 *
 * KNOWN GAP (reported, not solved here): the attempt-level
 * evaluation_status (NOT_REQUIRED/PENDING/PARTIAL/COMPLETE/
 * NEEDS_RECONCILIATION -- fold_in_attempt_evaluation(), 049) is not
 * exposed anywhere on GET /faculty/evaluations or its detail endpoint --
 * an evaluator who finalizes into a co-evaluation disagreement currently
 * has no way to learn that from this view. No reconciliation notice is
 * rendered here, since there is no real data to back one -- see the
 * Phase 2 implementation report's own Remaining Issues section.
 */

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; evaluation: EvaluationDetail; candidateRubrics: Rubric[] };

export function EvaluationDetailView({ evaluationId }: { evaluationId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  const [rubricId, setRubricId] = useState<string>("");
  const [marks, setMarks] = useState("");
  const [feedback, setFeedback] = useState("");

  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [transitioning, setTransitioning] = useState(false);
  const [transitionError, setTransitionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const evaluation = await getEvaluation(evaluationId);
        const candidateRubrics = evaluation.status === "FINALIZED" ? [] : await listCandidateRubrics(evaluationId);
        if (cancelled) return;
        setState({ status: "ready", evaluation, candidateRubrics });
        setRubricId(evaluation.rubric_id ?? "");
        setMarks(evaluation.awarded_marks ?? "");
        setFeedback(evaluation.feedback ?? "");
      } catch (err) {
        if (!cancelled) {
          setState({
            status: "error",
            error:
              err instanceof ApiError
                ? err
                : new ApiError(0, "Could not load this evaluation."),
          });
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [evaluationId, reloadKey]);

  const availableRubrics = useMemo(() => {
    if (state.status !== "ready") return [];
    const map = new Map(state.candidateRubrics.map((r) => [r.id, r]));
    if (state.evaluation.rubric && !map.has(state.evaluation.rubric.id)) {
      map.set(state.evaluation.rubric.id, state.evaluation.rubric);
    }
    return Array.from(map.values());
  }, [state]);

  const selectedRubric = availableRubrics.find((r) => r.id === rubricId) ?? null;

  function refetch() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function handleStart() {
    setTransitionError(null);
    setTransitioning(true);
    try {
      await updateEvaluationStatus(evaluationId, "IN_PROGRESS");
      toast.success("Evaluation started.");
      refetch();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not start this evaluation.";
      setTransitionError(message);
      toast.error(message);
      setTransitioning(false);
    }
  }

  async function handleSave() {
    setSaveError(null);
    setSaving(true);
    try {
      await saveEvaluation(evaluationId, {
        rubric_id: rubricId || null,
        awarded_marks: marks.trim() === "" ? null : marks.trim(),
        feedback: feedback.trim() === "" ? null : feedback.trim(),
      });
      toast.success("Evaluation draft saved.");
      refetch();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not save this evaluation.";
      setSaveError(message);
      toast.error(message);
      setSaving(false);
    }
  }

  async function handleSubmit() {
    setTransitionError(null);
    setTransitioning(true);
    try {
      await updateEvaluationStatus(evaluationId, "SUBMITTED");
      toast.success("Evaluation submitted.");
      refetch();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not submit this evaluation.";
      setTransitionError(message);
      toast.error(message);
      setTransitioning(false);
    }
  }

  async function handleFinalize() {
    setTransitionError(null);
    setTransitioning(true);
    try {
      await updateEvaluationStatus(evaluationId, "FINALIZED");
      toast.success("Evaluation finalized.");
      refetch();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Could not finalize this evaluation.";
      setTransitionError(message);
      toast.error(message);
      setTransitioning(false);
    }
  }

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-16 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading evaluation…
        </CardContent>
      </Card>
    );
  }

  if (state.status === "error") {
    const isForbiddenOrMissing = state.error.status === 403 || state.error.status === 404;
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-16 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">
              {isForbiddenOrMissing
                ? "This evaluation could not be found."
                : "Could not load this evaluation."}
            </p>
            <p className="text-sm text-muted-foreground">
              {isForbiddenOrMissing
                ? "It may not exist, or your assignment for it may have been revoked."
                : state.error.message}
            </p>
          </div>
          <div className="flex gap-2">
            {!isForbiddenOrMissing && (
              <Button size="sm" onClick={refetch}>
                Try again
              </Button>
            )}
            <Button
              variant="outline"
              size="sm"
              render={<Link href="/faculty/evaluation-workspace" />}
              nativeButton={false}
            >
              <ArrowLeft className="size-3.5" /> Back to Workspace
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const { evaluation } = state;
  const isFinalized = evaluation.status === "FINALIZED";
  const canEditContent = evaluation.status === "IN_PROGRESS" || evaluation.status === "SUBMITTED";
  const marksOutOfRange = Boolean(
    marks.trim() !== "" &&
      (Number.isNaN(Number(marks)) ||
        Number(marks) < 0 ||
        (selectedRubric !== null && Number(marks) > Number(selectedRubric.max_marks))),
  );

  return (
    <div className="flex flex-col gap-4">
      <Button
        variant="outline"
        size="sm"
        render={<Link href="/faculty/evaluation-workspace" />}
        nativeButton={false}
        className="self-start"
      >
        <ArrowLeft className="size-3.5" /> Back to Workspace
      </Button>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <div>
              <CardTitle className="text-lg">{evaluation.assessment_title}</CardTitle>
              <p className="text-xs text-muted-foreground">
                Assigned {new Date(evaluation.assigned_at).toLocaleDateString()}
              </p>
            </div>
            <EvaluationStatusBadge status={evaluation.status} />
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div>
            <p className="text-sm font-medium text-muted-foreground">Question</p>
            <p className="mt-1 text-base">{evaluation.question.question_text}</p>
            <p className="mt-1 text-sm text-muted-foreground">{evaluation.question.points} pts max</p>
          </div>

          {evaluation.question.options.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {evaluation.question.options.map((option) => (
                <li key={option.id} className="rounded-lg border border-border px-3 py-2 text-sm">
                  {option.option_text}
                </li>
              ))}
            </ul>
          )}

          <div>
            <p className="text-sm font-medium text-muted-foreground">Student Answer</p>
            {evaluation.student_answer?.answer_text ? (
              <p className="mt-1 whitespace-pre-wrap rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
                {evaluation.student_answer.answer_text}
              </p>
            ) : (
              <p className="mt-1 text-sm text-muted-foreground italic">No answer submitted.</p>
            )}
          </div>

          {evaluation.status === "ASSIGNED" && (
            <div className="rounded-lg border border-dashed p-4 text-center">
              <p className="text-sm text-muted-foreground">
                Start this evaluation to enter a rubric, marks, and feedback.
              </p>
            </div>
          )}

          {(canEditContent || isFinalized) && (
            <div className="flex flex-col gap-4 rounded-lg border p-4">
              <p className="text-sm font-medium">Rubric</p>
              {isFinalized ? (
                <RubricReadOnly rubric={evaluation.rubric} />
              ) : (
                <>
                  <div className="space-y-1.5">
                    <Label htmlFor="rubric-select">Choose a rubric</Label>
                    {availableRubrics.length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        No rubric has been set up for this question yet -- ask an Admin to add one.
                      </p>
                    ) : (
                      <Select
                        value={rubricId}
                        onValueChange={(next) => setRubricId(next ?? "")}
                        items={Object.fromEntries(availableRubrics.map((r) => [r.id, `${r.name} (${r.max_marks} pts)`]))}
                      >
                        <SelectTrigger id="rubric-select" className="w-full">
                          <SelectValue placeholder="Select a rubric" />
                        </SelectTrigger>
                        <SelectContent>
                          {availableRubrics.map((r) => (
                            <SelectItem key={r.id} value={r.id}>
                              {r.name} ({r.max_marks} pts)
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    )}
                  </div>
                  {selectedRubric && selectedRubric.criteria.length > 0 && (
                    <RubricReadOnly rubric={selectedRubric} />
                  )}
                  <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                    <div className="space-y-1.5">
                      <Label htmlFor="marks">
                        Marks {selectedRubric ? `(0 – ${selectedRubric.max_marks})` : ""}
                      </Label>
                      <Input
                        id="marks"
                        type="number"
                        min="0"
                        step="0.01"
                        value={marks}
                        onChange={(e) => setMarks(e.target.value)}
                        aria-invalid={marksOutOfRange || undefined}
                      />
                      {marksOutOfRange && (
                        <p className="text-xs text-destructive">
                          Marks must be between 0 and {selectedRubric ? selectedRubric.max_marks : "the maximum"}.
                        </p>
                      )}
                    </div>
                  </div>
                  <div className="space-y-1.5">
                    <Label htmlFor="feedback">Feedback</Label>
                    <Textarea
                      id="feedback"
                      value={feedback}
                      onChange={(e) => setFeedback(e.target.value)}
                      rows={3}
                      placeholder="Feedback for the student…"
                    />
                  </div>
                </>
              )}
            </div>
          )}

          {isFinalized && (
            <div className="rounded-lg border border-emerald-500/40 bg-emerald-500/10 px-3 py-2 text-sm">
              <p className="font-medium text-emerald-700 dark:text-emerald-400">
                Finalized {evaluation.finalized_at ? new Date(evaluation.finalized_at).toLocaleString() : ""}
              </p>
              <p className="mt-1">
                <span className="text-muted-foreground">Marks: </span>
                {evaluation.awarded_marks ?? "—"}
              </p>
              {evaluation.feedback && <p className="mt-1 whitespace-pre-wrap">{evaluation.feedback}</p>}
            </div>
          )}

          {saveError && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertCircle className="size-3.5 shrink-0" /> {saveError}
            </p>
          )}
          {transitionError && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertCircle className="size-3.5 shrink-0" /> {transitionError}
            </p>
          )}
        </CardContent>

        <CardFooter className="gap-2">
          {evaluation.status === "ASSIGNED" && (
            <Button onClick={() => void handleStart()} disabled={transitioning}>
              {transitioning && <Loader2 className="size-3.5 animate-spin" />} Start Evaluation
            </Button>
          )}
          {canEditContent && (
            <>
              <Button variant="outline" onClick={() => void handleSave()} disabled={saving || marksOutOfRange}>
                {saving && <Loader2 className="size-3.5 animate-spin" />} Save
              </Button>
              {evaluation.status === "IN_PROGRESS" && (
                <Button onClick={() => void handleSubmit()} disabled={transitioning}>
                  {transitioning && <Loader2 className="size-3.5 animate-spin" />} Submit
                </Button>
              )}
              {evaluation.status === "SUBMITTED" && (
                <Dialog>
                  <DialogTrigger render={<Button disabled={transitioning} />}>Finalize</DialogTrigger>
                  <DialogContent>
                    <DialogHeader>
                      <DialogTitle>Finalize Evaluation?</DialogTitle>
                      <DialogDescription>
                        After finalization, your evaluation will no longer be editable according to the
                        evaluation workflow. Are you sure?
                      </DialogDescription>
                    </DialogHeader>
                    <DialogFooter>
                      <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
                      <DialogClose render={<Button onClick={() => void handleFinalize()} />}>
                        Yes, finalize
                      </DialogClose>
                    </DialogFooter>
                  </DialogContent>
                </Dialog>
              )}
            </>
          )}
        </CardFooter>
      </Card>
    </div>
  );
}

function RubricReadOnly({ rubric }: { rubric: Rubric | null }) {
  if (!rubric) {
    return <p className="text-sm text-muted-foreground">No rubric selected.</p>;
  }
  return (
    <div className="space-y-2">
      <p className="text-sm font-medium">
        {rubric.name} <span className="text-muted-foreground">({rubric.max_marks} pts)</span>
      </p>
      {rubric.description && <p className="text-sm text-muted-foreground">{rubric.description}</p>}
      {rubric.criteria.length > 0 && (
        <ul className="flex flex-col gap-1.5">
          {rubric.criteria.map((c) => (
            <li key={c.id} className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-1.5 text-sm">
              <span>{c.criterion}</span>
              <Badge variant="outline">{c.max_marks} pts</Badge>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
