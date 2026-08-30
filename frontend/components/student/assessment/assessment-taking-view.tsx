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
  getAssessmentQuestions,
  getAttemptResult,
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
 * list -> start attempt -> answer questions -> submit -> trusted scoring
 * -> result. All values shown as authoritative (score, total_marks,
 * percentage, awarded_marks, is_correct) come directly from FastAPI
 * responses -- nothing here recalculates any of them.
 *
 * Per the approved Decision A: there is no backend endpoint to recover an
 * in-progress attempt. attemptId + confirmed answers are mirrored to
 * sessionStorage (lib/student/assessment-session.ts) purely so a
 * same-tab reload during one sitting can restore this component's UI
 * state -- if that storage is gone and the backend reports an
 * already-in-progress attempt, this shows an honest, unrecoverable state
 * rather than fabricating an attempt id or silently starting a new one.
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

  // ---- Initial load: assessment metadata + questions, then decide
  // whether a recoverable attempt already exists for this tab/session. ----
  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [assessmentData, questionData] = await Promise.all([
          getAssessment(assessmentId),
          getAssessmentQuestions(assessmentId),
        ]);
        if (cancelled) return;
        setAssessment(assessmentData);
        setQuestions(questionData);

        const stored = loadStoredAttempt(assessmentId);
        if (stored) {
          attemptIdRef.current = stored.attemptId;
          setAnswers(stored.answers);
          const confirmed = new Set(Object.keys(stored.answers));
          setConfirmedIds(confirmed);
          const states: Record<string, AnswerSaveState> = {};
          for (const qid of confirmed) states[qid] = "saved";
          setSaveStates(states);
          setStage({ name: "taking" });
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
      attemptIdRef.current = attempt.id;
      saveStoredAttempt({ assessmentId, attemptId: attempt.id, answers: {} });
      setStage({ name: "taking" });
    } catch (err) {
      if (err instanceof ApiError && err.status === 409) {
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
          <Badge variant="outline">{questions.length} questions</Badge>
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
  const { attempt, questions } = result;
  return (
    <div className="flex flex-col gap-5">
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">Assessment complete</CardTitle>
          <CardDescription>
            Submitted {attempt.submitted_at ? new Date(attempt.submitted_at).toLocaleString() : "—"}
          </CardDescription>
        </CardHeader>
        <CardContent className="flex flex-wrap gap-4">
          <Stat label="Score" value={`${attempt.score ?? "—"} / ${attempt.total_marks ?? "—"}`} />
          <Stat label="Percentage" value={attempt.percentage != null ? `${attempt.percentage}%` : "—"} />
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
