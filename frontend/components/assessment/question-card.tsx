"use client";

import { useState } from "react";
import { AlertCircle, Check, Loader2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { cn } from "@/lib/utils";
import type { SaveAnswerInput } from "@/lib/student/assessment";
import type { AssessmentQuestion } from "@/types/assessment";

export type AnswerSaveState = "idle" | "saving" | "saved" | "error";

interface QuestionCardProps {
  question: AssessmentQuestion;
  questionNumber: number;
  /** The student's current input for this question -- undefined means
   * nothing has been entered/saved yet for it. */
  value: SaveAnswerInput | undefined;
  /** Called with a *candidate* answer every time the student changes
   * their input. The parent (not this component) decides when/whether to
   * actually call the save API -- this component never calls the backend
   * itself and never fabricates a value the student didn't provide. */
  onChange: (input: SaveAnswerInput) => void;
  saveState: AnswerSaveState;
  saveError?: string;
  disabled?: boolean;
}

/** Renders one question for the currently-supported OBJECTIVE flow: MCQ
 * (single choice), MULTIPLE_SELECT (multiple choice), SHORT_ANSWER (free
 * text). Never shows correctness, never reveals the answer key -- this
 * component only ever renders AssessmentQuestion + AssessmentOption,
 * neither of which the backend can even include correctness data on. */
export function QuestionCard({
  question,
  questionNumber,
  value,
  onChange,
  saveState,
  saveError,
  disabled = false,
}: QuestionCardProps) {
  const selectedOptionIds = value?.selected_option_ids ?? [];

  function selectSingle(optionId: string) {
    onChange({ question_id: question.id, selected_option_ids: [optionId] });
  }

  function toggleMultiple(optionId: string) {
    const next = selectedOptionIds.includes(optionId)
      ? selectedOptionIds.filter((id) => id !== optionId)
      : [...selectedOptionIds, optionId];
    // The backend rejects an empty selected_option_ids array outright --
    // if the student deselects their last choice, hold the empty
    // selection locally (don't call onChange) rather than sending a
    // request the API will 422 on. The question simply stays unanswered
    // until at least one option is selected again.
    if (next.length === 0) return;
    onChange({ question_id: question.id, selected_option_ids: next });
  }

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="text-base leading-relaxed font-medium">
            <span className="text-muted-foreground">Q{questionNumber}.</span> {question.question_text}
          </CardTitle>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant="outline">{question.points} pts</Badge>
            <SaveStateIndicator state={saveState} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {question.question_type === "MCQ" && (
          <fieldset className="flex flex-col gap-2" disabled={disabled}>
            <legend className="sr-only">Choose one option</legend>
            {question.options.map((option) => (
              <label
                key={option.id}
                className={cn(
                  "flex cursor-pointer items-center gap-2.5 rounded-lg border border-border px-3 py-2 text-sm transition-colors hover:bg-muted",
                  selectedOptionIds.includes(option.id) && "border-primary bg-primary/5",
                  disabled && "cursor-not-allowed opacity-60",
                )}
              >
                <input
                  type="radio"
                  name={`question-${question.id}`}
                  value={option.id}
                  checked={selectedOptionIds.includes(option.id)}
                  onChange={() => selectSingle(option.id)}
                  disabled={disabled}
                  className="size-4 accent-primary"
                />
                {option.option_text}
              </label>
            ))}
          </fieldset>
        )}

        {question.question_type === "MULTIPLE_SELECT" && (
          <fieldset className="flex flex-col gap-2" disabled={disabled}>
            <legend className="text-xs text-muted-foreground">Select all that apply</legend>
            {question.options.map((option) => (
              <label
                key={option.id}
                className={cn(
                  "flex cursor-pointer items-center gap-2.5 rounded-lg border border-border px-3 py-2 text-sm transition-colors hover:bg-muted",
                  selectedOptionIds.includes(option.id) && "border-primary bg-primary/5",
                  disabled && "cursor-not-allowed opacity-60",
                )}
              >
                <input
                  type="checkbox"
                  name={`question-${question.id}`}
                  value={option.id}
                  checked={selectedOptionIds.includes(option.id)}
                  onChange={() => toggleMultiple(option.id)}
                  disabled={disabled}
                  className="size-4 accent-primary"
                />
                {option.option_text}
              </label>
            ))}
          </fieldset>
        )}

        {question.question_type === "SHORT_ANSWER" && (
          <ShortAnswerField
            key={question.id}
            questionId={question.id}
            value={value?.answer_text ?? ""}
            onChange={(text) => onChange({ question_id: question.id, answer_text: text })}
            disabled={disabled}
          />
        )}

        {saveState === "error" && saveError && (
          <div className="flex flex-wrap items-center gap-2 text-sm text-destructive">
            <AlertCircle className="size-3.5 shrink-0" />
            <span>{saveError}</span>
            {value && (
              <button
                type="button"
                onClick={() => onChange(value)}
                className="font-medium underline underline-offset-2 hover:no-underline"
              >
                Retry save
              </button>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}

function ShortAnswerField({
  questionId,
  value,
  onChange,
  disabled,
}: {
  questionId: string;
  value: string;
  onChange: (text: string) => void;
  disabled: boolean;
}) {
  // Local draft so keystrokes don't fight the parent's saved-value prop;
  // the parent only receives onChange on blur (see the page component for
  // why: SHORT_ANSWER saves on blur/navigate, not per-keystroke).
  const [draft, setDraft] = useState(value);

  return (
    <div className="flex flex-col gap-1.5">
      <Label htmlFor={`answer-${questionId}`}>Your answer</Label>
      <Input
        id={`answer-${questionId}`}
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onBlur={() => {
          if (draft.trim() !== "") onChange(draft);
        }}
        disabled={disabled}
        placeholder="Type your answer"
        autoComplete="off"
      />
    </div>
  );
}

function SaveStateIndicator({ state }: { state: AnswerSaveState }) {
  if (state === "saving") {
    return (
      <span className="flex items-center gap-1 text-xs text-muted-foreground">
        <Loader2 className="size-3 animate-spin" /> Saving
      </span>
    );
  }
  if (state === "saved") {
    return (
      <span className="flex items-center gap-1 text-xs text-emerald-600 dark:text-emerald-400">
        <Check className="size-3" /> Saved
      </span>
    );
  }
  if (state === "error") {
    return (
      <span className="flex items-center gap-1 text-xs text-destructive">
        <AlertCircle className="size-3" /> Not saved
      </span>
    );
  }
  return null;
}
