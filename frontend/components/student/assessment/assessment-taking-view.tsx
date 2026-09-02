"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, ArrowRight, CheckCircle2, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { AssessmentProgress } from "@/components/assessment/assessment-progress";
import { QuestionCard, type AnswerSaveState } from "@/components/assessment/question-card";
import { ResultCard } from "@/components/assessment/result-card";
import { ApiError } from "@/lib/api";
import {
  createAttempt,
  getAssessment,
  getAttemptQuestions,
  getAttemptResult,
  getCurrentAttempt,
  saveAnswer,
  scoreAttempt,
  submitAttempt,
  type SaveAnswerInput,
} from "@/lib/student/assessment";
import {
  clearStoredAttempt,
  loadStoredAttempt,
  saveStoredAnswer,
  saveStoredAttempt,
} from "@/lib/student/assessment-session";
import type { Assessment, AssessmentQuestion, AssessmentResult } from "@/types/assessment";

type Stage =
  | { name: "loading" }
  | { name: "load-error"; message: string }
  | { name: "ready-to-start" }
  | { name: "starting" }
  | { name: "already-in-progress" }
  | { name: "taking" }
  | { name: "confirming-submit" }
  | { name: "processing" }
  | { name: "result"; result: AssessmentResult };

interface ProcessingError {
  step: "submit" | "score" | "result";
  message: string;
}

function friendlyMessage(err: unknown): string {
  if (err instanceof ApiError) return err.message;
  return "Something went wrong. Please try again.";
}

/** Owns the whole student-facing lifecycle for one assessment:
 * list -> start/resume attempt -> answer questions -> submit -> trusted
 * scoring -> result. All values shown as authoritative (score,
 * total_marks, percentage, passed, skill_verified, awarded_marks,
 * is_correct) come directly from FastAPI responses -- nothing here
 * recalculates any of them, and the question set itself is never
 * randomized or reordered client-side (015_assessment_verification.sql's
 * create_assessment_attempt() does that server-side, once, and freezes
 * it).
 *
 * Resume is real: GET /assessments/{id}/attempts/current confirms an
 * in-progress attempt against the backend (not just this tab's storage),
 * and GET /attempts/{id}/questions always returns that exact attempt's
 * frozen question set. sessionStorage (lib/student/assessment-session.ts)
 * is used only for the narrower, still-unsolved problem of repainting
 * which answers were already saved on THIS device -- there is no backend
 * endpoint to list a student's own saved answers for an attempt, so a
 * resume from a different device shows the right questions but not prior
 * selections (they are still safely saved server-side and unaffected).
 * The "already-in-progress, cannot be recovered" state is now reached
 * only if the backend's own resume lookup also fails right after a 409.
 */
export function AssessmentTakingView({ assessmentId }: { assessmentId: string }) {
  const [stage, setStage] = useState<Stage>({ name: "loading" });
  const [assessment, setAssessment] = useState<Assessment | null>(null);
  const [questions, setQuestions] = useState<AssessmentQuestion[]>([]);
  const [startError, setStartError] = useState<string | null>(null);

  const attemptIdRef = useRef<string | null>(null);
  const [currentIndex, setCurrentIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, SaveAnswerInput>>({});
  const [saveStates, setSaveStates] = useState<Record<string, AnswerSaveState>>({});
  const [saveErrors, setSaveErrors] = useState<Record<string, string>>({});
  const [confirmedIds, setConfirmedIds] = useState<Set<string>>(new Set());

  const submittedRef = useRef(false);
  const scoredRef = useRef(false);
  const processingInFlightRef = useRef(false);
  const [processingError, setProcessingError] = useState<ProcessingError | null>(null);

  // ---- Initial load: assessment metadata, then check the backend for a
  // real in-progress attempt (GET .../attempts/current) -- not just this
  // tab's sessionStorage -- and resume it by fetching its FROZEN question
  // set (GET /attempts/{id}/questions). Refreshing, resuming on another
  // tab, or reopening later all return exactly the same questions in
  // exactly the same order, because that read is a permanent historical
  // record, never a live re-query against the question bank. ----
  useEffect(() => {
    let cancelled = false;

    async function resumeInto(attemptId: string) {
      const questionData = await getAttemptQuestions(attemptId);
      if (cancelled) return;
      attemptIdRef.current = attemptId;
      setQuestions(questionData);

      const stored = loadStoredAttempt(assessmentId);
      if (stored && stored.attemptId === attemptId) {
        setAnswers(stored.answers);
        const confirmed = new Set(Object.keys(stored.answers));
        setConfirmedIds(confirmed);
        const states: Record<string, AnswerSaveState> = {};
        for (const qid of confirmed) states[qid] = "saved";
        setSaveStates(states);
      } else {
        // A real in-progress attempt exists (confirmed by the backend),
        // but this device/tab has no local record of which answers were
        // already saved -- the taking UI still works correctly (answers
        // save/overwrite idempotently), it just can't repaint prior
        // selections. Re-anchor local storage to this attempt so further
        // answers on this device are tracked from here on.
        saveStoredAttempt({ assessmentId, attemptId, answers: {} });
      }
      setStage({ name: "taking" });
    }

    async function load() {
      try {
        const assessmentData = await getAssessment(assessmentId);
        if (cancelled) return;
        setAssessment(assessmentData);

        const current = await getCurrentAttempt(assessmentId);
        if (cancelled) return;

        if (current) {
          await resumeInto(current.id);
        } else {
          setStage({ name: "ready-to-start" });
        }
      } catch (err) {
        if (cancelled) return;
        setStage({
          name: "load-error",
          message:
            err instanceof ApiError && err.status === 404
              ? "This assessment doesn't exist or is no longer available."
              : friendlyMessage(err),
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [assessmentId]);

  async function handleStart() {
    setStage({ name: "starting" });
    setStartError(null);
    try {
      const attempt = await createAttempt(assessmentId);
      const questionData = await getAttemptQuestions(attempt.id);
      attemptIdRef.current = attempt.id;
      setQuestions(questionData);
      saveStoredAttempt({ assessmentId, attemptId: attempt.id, answers: {} });
      setStage({ name: "taking" });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
        // Lost a race (e.g. a double-click, or another tab already
        // started one) -- the backend confirms a real in-progress attempt
        // exists, so resume it properly instead of a dead-end message.
        try {
          const current = await getCurrentAttempt(assessmentId);
          if (current) {
            const questionData = await getAttemptQuestions(current.id);
            attemptIdRef.current = current.id;
            setQuestions(questionData);
            saveStoredAttempt({ assessmentId, attemptId: current.id, answers: {} });
            setStage({ name: "taking" });
            return;
          }
        } catch {
          // Fall through to the honest "cannot be recovered" state below.
        }
        setStage({ name: "already-in-progress" });
        return;
      }
      setStartError(friendlyMessage(err));
      setStage({ name: "ready-to-start" });
    }
  }

  async function handleAnswerChange(input: SaveAnswerInput) {
    const attemptId = attemptIdRef.current;
    if (!attemptId) return;

    setAnswers((prev) => ({ ...prev, [input.question_id]: input }));
    setSaveStates((prev) => ({ ...prev, [input.question_id]: "saving" }));
    setSaveErrors((prev) => {
      const next = { ...prev };
      delete next[input.question_id];
      return next;
    });

    try {
      await saveAnswer(attemptId, input);
      setSaveStates((prev) => ({ ...prev, [input.question_id]: "saved" }));
      setConfirmedIds((prev) => new Set(prev).add(input.question_id));
      saveStoredAnswer(assessmentId, attemptId, input);
    } catch (err) {
      // Local input (already applied above) is preserved on failure; the
      // question is NOT marked confirmed/answered, so progress/submit
      // gating stays accurate to what the backend actually has.
      setSaveStates((prev) => ({ ...prev, [input.question_id]: "error" }));
      setSaveErrors((prev) => ({ ...prev, [input.question_id]: friendlyMessage(err) }));
    }
  }

  async function runProcessing() {
    const attemptId = attemptIdRef.current;
    // Guards against a double-click/double-invocation submitting twice:
    // this ref is only true while an attempt is actually in flight
    // (distinct from `stage.name === "processing"`, which also covers the
    // "landed on a retryable error, waiting for Try again" state).
    if (!attemptId || processingInFlightRef.current) return;
    processingInFlightRef.current = true;
    setStage({ name: "processing" });
    setProcessingError(null);

    try {
      if (!submittedRef.current) {
        try {
          await submitAttempt(attemptId);
          submittedRef.current = true;
        } catch (err) {
          setProcessingError({ step: "submit", message: friendlyMessage(err) });
          return;
        }
      }

      if (!scoredRef.current) {
        try {
          await scoreAttempt(attemptId);
          scoredRef.current = true;
          clearStoredAttempt(assessmentId);
        } catch (err) {
          setProcessingError({ step: "score", message: friendlyMessage(err) });
          return;
        }
      }

      try {
        const result = await getAttemptResult(attemptId);
        setStage({ name: "result", result });
      } catch (err) {
        setProcessingError({ step: "result", message: friendlyMessage(err) });
      }
    } finally {
      processingInFlightRef.current = false;
    }
  }

  // ---------------------------------------------------------------------

  if (stage.name === "loading") {
    return <LoadingCard label="Loading assessment…" />;
  }

  if (stage.name === "load-error") {
    return <ErrorCard message={stage.message} />;
  }

  if (stage.name === "already-in-progress") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-muted-foreground" />
          <div>
            <p className="font-medium">You already have an assessment in progress.</p>
            <p className="text-sm text-muted-foreground">
              This attempt cannot be recovered from this device.
            </p>
          </div>
          <Button
            variant="outline"
            size="sm"
            render={<Link href="/student/assessment" />}
            nativeButton={false}
          >
            <ArrowLeft className="size-3.5" /> Back to assessments
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (stage.name === "ready-to-start" || stage.name === "starting") {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">{assessment?.title}</CardTitle>
          {assessment?.description && <CardDescription>{assessment.description}</CardDescription>}
        </CardHeader>
        <CardContent className="flex flex-wrap gap-2">
          <Badge variant="outline">{assessment?.difficulty}</Badge>
          {assessment?.duration_minutes != null && (
            <Badge variant="outline">{assessment.duration_minutes} min</Badge>
          )}
          {assessment?.question_count != null && (
            <Badge variant="outline">{assessment.question_count} questions</Badge>
          )}
          {assessment?.passing_percentage != null && (
            <Badge variant="outline">Passing score: {assessment.passing_percentage}%</Badge>
          )}
        </CardContent>
        <CardFooter className="flex-col items-stretch gap-2">
          {startError && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertCircle className="size-3.5 shrink-0" /> {startError}
            </p>
          )}
          <Button onClick={handleStart} disabled={stage.name === "starting"}>
            {stage.name === "starting" && <Loader2 className="size-3.5 animate-spin" />}
            Start assessment
          </Button>
        </CardFooter>
      </Card>
    );
  }

  if (stage.name === "processing") {
    if (processingError) {
      return (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" />
            <div>
              <p className="font-medium">
                {processingError.step === "submit" && "Could not submit your assessment."}
                {processingError.step === "score" && "Your assessment was submitted, but scoring failed."}
                {processingError.step === "result" && "Your assessment was scored, but the result couldn't be loaded."}
              </p>
              <p className="text-sm text-muted-foreground">{processingError.message}</p>
            </div>
            <Button size="sm" onClick={runProcessing}>
              Try again
            </Button>
          </CardContent>
        </Card>
      );
    }
    return (
      <LoadingCard
        label={
          !submittedRef.current
            ? "Submitting your assessment…"
            : !scoredRef.current
              ? "Scoring your assessment…"
              : "Loading your result…"
        }
      />
    );
  }

  if (stage.name === "result") {
    return <AssessmentResultView result={stage.result} />;
  }

  // stage.name === "taking" | "confirming-submit"
  const currentQuestion = questions[currentIndex];
  const answeredCount = confirmedIds.size;
  const allAnswered = questions.length > 0 && answeredCount === questions.length;

  return (
    <div className="flex flex-col gap-5">
      <AssessmentProgress current={currentIndex + 1} total={questions.length} answeredCount={answeredCount} />

      {currentQuestion && (
        <QuestionCard
          key={currentQuestion.id}
          question={currentQuestion}
          questionNumber={currentIndex + 1}
          value={answers[currentQuestion.id]}
          onChange={handleAnswerChange}
          saveState={saveStates[currentQuestion.id] ?? "idle"}
          saveError={saveErrors[currentQuestion.id]}
          disabled={stage.name === "confirming-submit"}
        />
      )}

      <div className="flex items-center justify-between gap-3">
        <Button
          variant="outline"
          onClick={() => setCurrentIndex((i) => Math.max(0, i - 1))}
          disabled={currentIndex === 0}
        >
          <ArrowLeft className="size-3.5" /> Previous
        </Button>

        {currentIndex < questions.length - 1 ? (
          <Button
            onClick={() => setCurrentIndex((i) => Math.min(questions.length - 1, i + 1))}
          >
            Next <ArrowRight className="size-3.5" />
          </Button>
        ) : stage.name === "confirming-submit" ? (
          <div className="flex items-center gap-2">
            <Button variant="outline" onClick={() => setStage({ name: "taking" })}>
              Cancel
            </Button>
            <Button onClick={runProcessing}>
              <CheckCircle2 className="size-3.5" /> Confirm submit
            </Button>
          </div>
        ) : (
          <Button
            onClick={() => setStage({ name: "confirming-submit" })}
            disabled={!allAnswered}
            title={allAnswered ? undefined : "Answer every question before submitting"}
          >
            Submit assessment
          </Button>
        )}
      </div>

      {!allAnswered && currentIndex === questions.length - 1 && stage.name === "taking" && (
        <p className="text-sm text-muted-foreground">
          Answer all {questions.length} questions to submit ({answeredCount} of {questions.length} so far).
        </p>
      )}
    </div>
  );
}

function AssessmentResultView({ result }: { result: AssessmentResult }) {
  const { attempt, passed, skill_verified, questions } = result;
  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between gap-2">
            <CardTitle className="text-lg">Assessment complete</CardTitle>
            <Badge
              variant="outline"
              className={
                passed
                  ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400"
                  : "border-destructive/30 bg-destructive/10 text-destructive"
              }
            >
              {passed ? "PASSED" : "NOT PASSED"}
            </Badge>
          </div>
          <CardDescription>
            Submitted {attempt.submitted_at ? new Date(attempt.submitted_at).toLocaleString() : "—"}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="flex flex-wrap items-center gap-4">
            <Stat label="Score" value={`${attempt.score ?? "—"} / ${attempt.total_marks ?? "—"}`} />
            <Stat label="Percentage" value={attempt.percentage != null ? `${attempt.percentage}%` : "—"} />
            <div className="flex items-center gap-1.5 text-sm">
              {skill_verified ? (
                <>
                  <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
                  <span className="text-emerald-600 dark:text-emerald-400">Skill Verified</span>
                </>
              ) : (
                <span className="text-muted-foreground">Skill remains unverified</span>
              )}
            </div>
          </div>
          {passed && !skill_verified && (
            <p className="text-xs text-muted-foreground">
              Passing an assessment verifies a skill only when it is already in your profile at this
              exact level. Add it under Skills &amp; Assessment (or set the matching level), then
              retake to verify — an assessment never creates a skill on its own.
            </p>
          )}
        </CardContent>
        <CardFooter>
          <Button
            variant="outline"
            size="sm"
            render={<Link href="/student/assessment" />}
            nativeButton={false}
          >
            <ArrowLeft className="size-3.5" /> Back to assessments
          </Button>
        </CardFooter>
      </Card>

      <div className="flex flex-col gap-4">
        {questions.map((q, i) => (
          <ResultCard key={q.question.id} result={q} questionNumber={i + 1} />
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="text-2xl font-semibold tabular-nums">{value}</p>
    </div>
  );
}

function LoadingCard({ label }: { label: string }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground" aria-busy="true">
        <Loader2 className="size-6 animate-spin" />
        <p className="text-sm">{label}</p>
      </CardContent>
    </Card>
  );
}

function ErrorCard({ message }: { message: string }) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
        <AlertCircle className="size-8 text-destructive" />
        <p className="font-medium">{message}</p>
        <Button
          variant="outline"
          size="sm"
          render={<Link href="/student/assessment" />}
          nativeButton={false}
        >
          <ArrowLeft className="size-3.5" /> Back to assessments
        </Button>
      </CardContent>
    </Card>
  );
}
