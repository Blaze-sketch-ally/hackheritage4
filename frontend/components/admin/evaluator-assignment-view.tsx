"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Loader2, RefreshCw, UserPlus, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  createEvaluatorAssignment,
  listAttemptsForAssignment,
  listEligibleEvaluators,
  revokeEvaluatorAssignment,
} from "@/lib/admin/evaluator-assignments";
import { listAssessmentsForFaculty } from "@/lib/faculty/question-bank";
import { ApiError } from "@/lib/api";
import type { Assessment } from "@/types/assessment";
import type { AttemptForAssignment, EligibleEvaluator } from "@/types/evaluation";

/**
 * Phase 2: ADMIN-only evaluator-assignment management --
 * app.api.admin_evaluator_assignments.py, gated by require_admin().
 * Assessment selection reuses the existing GET /assessments endpoint
 * (lib/faculty/question-bank.ts's listAssessmentsForFaculty -- the
 * identical, already-existing, role-agnostic "authenticated can view
 * active assessments" read, not a new admin-only listing) rather than
 * duplicating it.
 *
 * KNOWN, PRE-EXISTING LIMITATION (not introduced by this component):
 * app/admin/layout.tsx's own comment already documents that there is
 * currently no way to provision a real ADMIN account through the app
 * (002_protect_admin_role.sql) -- this page, like the pre-existing
 * /admin/faculty capability-management page, is reachable only once an
 * ADMIN profile exists (e.g. seeded directly). See the Phase 2
 * implementation report's own Remaining Issues section.
 */

type AssessmentLoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; assessments: Assessment[]; evaluators: EligibleEvaluator[] };

type AttemptsLoadState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; attempts: AttemptForAssignment[] };

export function EvaluatorAssignmentView() {
  const [topState, setTopState] = useState<AssessmentLoadState>({ status: "loading" });
  const [assessmentId, setAssessmentId] = useState("");
  const [attemptsState, setAttemptsState] = useState<AttemptsLoadState>({ status: "idle" });
  const [reloadKey, setReloadKey] = useState(0);

  const [selectedEvaluator, setSelectedEvaluator] = useState<Record<string, string>>({});
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [{ assessments }, evaluators] = await Promise.all([
          listAssessmentsForFaculty(),
          listEligibleEvaluators(),
        ]);
        if (!cancelled) setTopState({ status: "ready", assessments, evaluators });
      } catch (err) {
        if (!cancelled) {
          setTopState({
            status: "error",
            message: err instanceof ApiError ? err.message : "Could not load assessments/evaluators.",
          });
        }
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!assessmentId) {
      return;
    }
    let cancelled = false;
    listAttemptsForAssignment(assessmentId)
      .then((attempts) => {
        if (!cancelled) setAttemptsState({ status: "ready", attempts });
      })
      .catch((err: unknown) => {
        if (!cancelled) {
          setAttemptsState({
            status: "error",
            message: err instanceof ApiError ? err.message : "Could not load attempts for this assessment.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [assessmentId, reloadKey]);

  function selectAssessment(nextId: string) {
    setAssessmentId(nextId);
    setAttemptsState(nextId ? { status: "loading" } : { status: "idle" });
  }

  function refetchAttempts() {
    setAttemptsState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function handleAssign(attemptId: string, questionId: string) {
    const key = `${attemptId}:${questionId}`;
    const evaluatorId = selectedEvaluator[key];
    if (!evaluatorId) return;
    setActionError(null);
    setBusyKey(key);
    try {
      await createEvaluatorAssignment({ evaluator_id: evaluatorId, attempt_id: attemptId, question_id: questionId });
      refetchAttempts();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not create this assignment.");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleRevoke(assignmentId: string) {
    setActionError(null);
    setBusyKey(assignmentId);
    try {
      await revokeEvaluatorAssignment(assignmentId);
      refetchAttempts();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not revoke this assignment.");
    } finally {
      setBusyKey(null);
    }
  }

  if (topState.status === "loading") {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading…
        </CardContent>
      </Card>
    );
  }

  if (topState.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <p className="font-medium">{topState.message}</p>
        </CardContent>
      </Card>
    );
  }

  const { assessments, evaluators } = topState;

  return (
    <div className="flex flex-col gap-4">
      <div className="space-y-1.5">
        <label htmlFor="assessment-select" className="text-sm font-medium">
          Assessment
        </label>
        {assessments.length === 0 ? (
          <p className="text-sm text-muted-foreground">No active assessments found.</p>
        ) : (
          <Select
            value={assessmentId}
            onValueChange={(next) => selectAssessment(next ?? "")}
            items={Object.fromEntries(assessments.map((a) => [a.id, a.title]))}
          >
            <SelectTrigger id="assessment-select" className="w-full sm:w-80">
              <SelectValue placeholder="Choose an assessment" />
            </SelectTrigger>
            <SelectContent>
              {assessments.map((a) => (
                <SelectItem key={a.id} value={a.id}>
                  {a.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}
      </div>

      {actionError && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="size-3.5 shrink-0" /> {actionError}
        </p>
      )}

      {evaluators.length === 0 && assessmentId && (
        <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
          <AlertCircle className="size-3.5 shrink-0" /> No Faculty currently hold the Evaluator capability -- grant
          it under Faculty assessment permissions first.
        </p>
      )}

      {attemptsState.status === "loading" && (
        <Card>
          <CardContent className="flex items-center justify-center gap-2 py-8 text-muted-foreground" aria-busy="true">
            <Loader2 className="size-5 animate-spin" /> Loading attempts…
          </CardContent>
        </Card>
      )}

      {attemptsState.status === "error" && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
            <AlertCircle className="size-6 text-destructive" />
            <p className="text-sm text-muted-foreground">{attemptsState.message}</p>
            <Button variant="outline" size="sm" onClick={refetchAttempts}>
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          </CardContent>
        </Card>
      )}

      {attemptsState.status === "ready" && (
        <>
          {attemptsState.attempts.length === 0 ? (
            <Card>
              <CardContent className="py-8 text-center text-sm text-muted-foreground">
                No completed attempts with an AI-evaluated question exist yet for this assessment.
              </CardContent>
            </Card>
          ) : (
            <div className="flex flex-col gap-4">
              {attemptsState.attempts.map((attempt) => (
                <Card key={attempt.attempt_id}>
                  <CardContent className="flex flex-col gap-3">
                    <p className="text-sm font-medium">{attempt.student_label}</p>
                    {attempt.questions.map((question) => {
                      const key = `${attempt.attempt_id}:${question.question_id}`;
                      const busy = busyKey === key;
                      return (
                        <div key={question.question_id} className="rounded-lg border p-3">
                          <p className="line-clamp-2 text-sm">{question.question_text}</p>
                          <p className="text-xs text-muted-foreground">{question.points} pts</p>

                          {question.existing_assignments.length > 0 && (
                            <ul className="mt-2 flex flex-col gap-1.5">
                              {question.existing_assignments.map((a) => (
                                <li
                                  key={a.assignment_id}
                                  className="flex items-center justify-between gap-2 rounded-lg bg-muted/50 px-2.5 py-1.5 text-xs"
                                >
                                  <span className="min-w-0 truncate">
                                    {a.evaluator_full_name || a.evaluator_email}
                                  </span>
                                  <div className="flex shrink-0 items-center gap-1.5">
                                    <Badge variant="outline">{a.evaluation_status}</Badge>
                                    {a.assignment_status === "ACTIVE" ? (
                                      <Button
                                        size="sm"
                                        variant="outline"
                                        disabled={busyKey === a.assignment_id}
                                        onClick={() => void handleRevoke(a.assignment_id)}
                                      >
                                        <X className="size-3" /> Revoke
                                      </Button>
                                    ) : (
                                      <Badge variant="secondary">Revoked</Badge>
                                    )}
                                  </div>
                                </li>
                              ))}
                            </ul>
                          )}

                          <div className="mt-2 flex items-center gap-2">
                            <Select
                              value={selectedEvaluator[key] ?? ""}
                              onValueChange={(next) =>
                                setSelectedEvaluator((prev) => ({ ...prev, [key]: next ?? "" }))
                              }
                              items={Object.fromEntries(
                                evaluators.map((e) => [e.faculty_id, e.full_name || e.email]),
                              )}
                            >
                              <SelectTrigger className="w-full sm:w-64">
                                <SelectValue placeholder="Assign an evaluator…" />
                              </SelectTrigger>
                              <SelectContent>
                                {evaluators.map((e) => (
                                  <SelectItem key={e.faculty_id} value={e.faculty_id}>
                                    {e.full_name || e.email}
                                  </SelectItem>
                                ))}
                              </SelectContent>
                            </Select>
                            <Button
                              size="sm"
                              disabled={!selectedEvaluator[key] || busy}
                              onClick={() => void handleAssign(attempt.attempt_id, question.question_id)}
                            >
                              {busy ? <Loader2 className="size-3.5 animate-spin" /> : <UserPlus className="size-3.5" />}
                              Assign
                            </Button>
                          </div>
                        </div>
                      );
                    })}
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
