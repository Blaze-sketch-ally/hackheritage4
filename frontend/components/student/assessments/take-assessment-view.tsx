"use client";

import { useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { FormError } from "@/components/auth/form-error";
import { Progress } from "@/components/ui/progress";
import { cn } from "@/lib/utils";
import { createClient } from "@/lib/supabase/client";
import {
  getAssessmentErrorMessage,
  saveAnswer,
  scoreAttemptViaBackend,
  submitAttempt,
  type Assessment,
  type AssessmentAnswer,
  type AssessmentAttempt,
  type AssessmentQuestion,
} from "@/lib/student/assessments";

type LocalAnswer = { answerText: string; selectedOptionIds: string[] };

function toLocalAnswer(answer: AssessmentAnswer | undefined): LocalAnswer {
  return {
    answerText: answer?.answer_text ?? "",
    selectedOptionIds: answer?.selected_option_ids ?? [],
  };
}

export function TakeAssessmentView({
  assessment,
  attempt,
  questions,
  initialAnswers,
}: {
  assessment: Assessment;
  attempt: AssessmentAttempt;
  questions: AssessmentQuestion[];
  initialAnswers: AssessmentAnswer[];
}) {
  const router = useRouter();
  const [index, setIndex] = useState(0);
  const [answers, setAnswers] = useState<Record<string, LocalAnswer>>(() => {
    const map: Record<string, LocalAnswer> = {};
    for (const q of questions) {
      map[q.id] = toLocalAnswer(initialAnswers.find((a) => a.question_id === q.id));
    }
    return map;
  });
  const [savingQuestionId, setSavingQuestionId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);

  const question = questions[index];
  const total = questions.length;

  const answeredCount = useMemo(
    () =>
      questions.filter((q) => {
        const a = answers[q.id];
        return a && (a.answerText.trim() !== "" || a.selectedOptionIds.length > 0);
      }).length,
    [questions, answers],
  );

  async function persistAnswer(questionId: string, next: LocalAnswer) {
    setSavingQuestionId(questionId);
    setError(null);
    try {
      const supabase = createClient();
      const { error: saveError } = await saveAnswer(supabase, attempt.id, questionId, {
        answerText: next.answerText.trim() || null,
        selectedOptionIds: next.selectedOptionIds.length > 0 ? next.selectedOptionIds : null,
      });
      if (saveError) {
        setError(getAssessmentErrorMessage(saveError));
      }
    } catch (err) {
      console.error("Save answer failed:", err);
      setError(getAssessmentErrorMessage(err));
    } finally {
      setSavingQuestionId(null);
    }
  }

  function selectOption(optionId: string, multi: boolean) {
    const current = answers[question.id];
    const next: LocalAnswer = multi
      ? {
          ...current,
          selectedOptionIds: current.selectedOptionIds.includes(optionId)
            ? current.selectedOptionIds.filter((id) => id !== optionId)
            : [...current.selectedOptionIds, optionId],
        }
      : { ...current, selectedOptionIds: [optionId] };

    setAnswers((prev) => ({ ...prev, [question.id]: next }));
    void persistAnswer(question.id, next);
  }

  function updateText(text: string) {
    setAnswers((prev) => ({ ...prev, [question.id]: { ...prev[question.id], answerText: text } }));
  }

  function saveTextOnBlur() {
    void persistAnswer(question.id, answers[question.id]);
  }

  async function handleSubmit() {
    setSubmitting(true);
    setError(null);
    try {
      const supabase = createClient();
      const { error: submitError } = await submitAttempt(supabase, attempt.id);
      if (submitError) {
        setError(getAssessmentErrorMessage(submitError));
        return;
      }
      // Ask the backend to authoritatively score + complete the attempt.
      // Its own failure isn't treated as blocking here: submitted_at is
      // already persisted by submitAttempt() above, so even if scoring
      // can't be reached right now, the student still lands on a result
      // page that honestly shows "submitted, awaiting scoring" rather
      // than losing their submission or getting stuck on an error.
      await scoreAttemptViaBackend(supabase, attempt.id);
      router.push(`/student/assessments/${assessment.id}/result?attemptId=${attempt.id}`);
    } catch (err) {
      console.error("Submit assessment failed:", err);
      setError(getAssessmentErrorMessage(err));
    } finally {
      setSubmitting(false);
      setConfirmOpen(false);
    }
  }

  if (!question) {
    return (
      <div className="rounded-xl border border-dashed px-6 py-16 text-center text-sm text-muted-foreground">
        This assessment has no questions yet. Please check back later.
      </div>
    );
  }

  const currentAnswer = answers[question.id];
  const isMulti = question.question_type === "MULTIPLE_SELECT";
  const isChoice = question.question_type === "MCQ" || isMulti;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">{assessment.title}</h1>
          <p className="text-sm text-muted-foreground">
            Question {index + 1} of {total} &middot; {answeredCount} of {total} answered
          </p>
        </div>
        <Button variant="outline" onClick={() => setConfirmOpen(true)}>
          Submit Assessment
        </Button>
      </div>

      <Progress value={(answeredCount / total) * 100} aria-label="Answered progress" />

      <div className="flex flex-wrap gap-2">
        {questions.map((q, i) => {
          const a = answers[q.id];
          const isAnswered = a && (a.answerText.trim() !== "" || a.selectedOptionIds.length > 0);
          return (
            <button
              key={q.id}
              type="button"
              onClick={() => setIndex(i)}
              aria-label={`Go to question ${i + 1}${isAnswered ? " (answered)" : " (unanswered)"}`}
              aria-current={i === index}
              className={cn(
                "flex size-8 items-center justify-center rounded-lg text-xs font-medium transition-colors",
                i === index
                  ? "bg-primary text-primary-foreground"
                  : isAnswered
                    ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
                    : "border border-dashed text-muted-foreground",
              )}
            >
              {i + 1}
            </button>
          );
        })}
      </div>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-2">
            <CardTitle className="text-base leading-snug font-medium">{question.question_text}</CardTitle>
            <Badge variant="outline">{question.points} pt{question.points === 1 ? "" : "s"}</Badge>
          </div>
        </CardHeader>
        <CardContent className="space-y-3">
          {isChoice ? (
            <div className="space-y-2" role={isMulti ? "group" : "radiogroup"} aria-label="Answer options">
              {question.options.map((option) => {
                const selected = currentAnswer.selectedOptionIds.includes(option.id);
                return (
                  <button
                    key={option.id}
                    type="button"
                    role={isMulti ? "checkbox" : "radio"}
                    aria-checked={selected}
                    onClick={() => selectOption(option.id, isMulti)}
                    className={cn(
                      "flex w-full items-center gap-3 rounded-lg border px-3 py-2.5 text-left text-sm transition-colors",
                      selected
                        ? "border-primary bg-indigo-500/10 text-foreground"
                        : "border-border/60 hover:bg-muted",
                    )}
                  >
                    <span
                      className={cn(
                        "flex size-4 shrink-0 items-center justify-center border",
                        isMulti ? "rounded-[4px]" : "rounded-full",
                        selected ? "border-primary bg-primary" : "border-input",
                      )}
                      aria-hidden="true"
                    >
                      {selected ? <span className="size-1.5 rounded-full bg-primary-foreground" /> : null}
                    </span>
                    {option.option_text}
                  </button>
                );
              })}
            </div>
          ) : (
            <textarea
              value={currentAnswer.answerText}
              onChange={(e) => updateText(e.target.value)}
              onBlur={saveTextOnBlur}
              placeholder="Type your answer here..."
              rows={6}
              aria-label="Your answer"
              className="w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          )}

          {savingQuestionId === question.id ? (
            <p className="text-xs text-muted-foreground">Saving...</p>
          ) : null}
        </CardContent>
      </Card>

      <FormError message={error} />

      <div className="flex items-center justify-between">
        <Button variant="outline" onClick={() => setIndex((i) => Math.max(0, i - 1))} disabled={index === 0}>
          <ChevronLeft /> Previous
        </Button>
        <Button
          variant="outline"
          onClick={() => setIndex((i) => Math.min(total - 1, i + 1))}
          disabled={index === total - 1}
        >
          Next <ChevronRight />
        </Button>
      </div>

      <ConfirmationDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title={`You have answered ${answeredCount} of ${total} questions.`}
        description="Are you sure you want to submit? You won't be able to change your answers after this."
        confirmLabel="Submit"
        loading={submitting}
        onConfirm={handleSubmit}
      />
    </div>
  );
}
