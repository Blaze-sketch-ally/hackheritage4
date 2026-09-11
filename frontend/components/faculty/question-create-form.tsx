"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { AlertCircle, Loader2, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiError } from "@/lib/api";
import { toast } from "sonner";
import { createQuestion, listAssessmentsForFaculty } from "@/lib/faculty/question-bank";
import type { Assessment, Difficulty, QuestionType } from "@/types/assessment";
import type { QuestionOptionInput } from "@/types/question-bank";

const DIFFICULTIES: Difficulty[] = ["Beginner", "Intermediate", "Advanced", "Expert"];
const DIFFICULTY_ITEMS: Record<Difficulty, string> = {
  Beginner: "Beginner",
  Intermediate: "Intermediate",
  Advanced: "Advanced",
  Expert: "Expert",
};

/** Only these three types have a working end-to-end scoring path
 * (score_assessment_attempt() and the review_question() approval-readiness
 * guard, 043_question_authoring_metadata.sql, both only implement these
 * three) -- CODE/SUBJECTIVE are valid `question_type` CHECK-constraint
 * values with no scoring engine behind them, so they are deliberately not
 * offered here rather than silently accepted and later blocked at
 * approval time. */
const QUESTION_TYPES: QuestionType[] = ["MCQ", "MULTIPLE_SELECT", "SHORT_ANSWER"];
const QUESTION_TYPE_ITEMS: Record<QuestionType, string> = {
  MCQ: "Multiple choice (one correct answer)",
  MULTIPLE_SELECT: "Multiple select (several correct answers)",
  SHORT_ANSWER: "Short answer",
  CODE: "Code",
  SUBJECTIVE: "Subjective",
};

interface OptionDraft extends QuestionOptionInput {
  id: string;
}

function newOption(order: number): OptionDraft {
  return { id: crypto.randomUUID(), option_text: "", display_order: order };
}

/** Only OBJECTIVE questions are offered here -- AI_EVALUATED has no
 * scoring path anywhere in this system yet (see
 * score_assessment_attempt()'s own header comment), so creating one would
 * produce a question that can never actually be scored. Every question
 * created through this form is submitted OBJECTIVE, PENDING (never
 * self-approved), owned by the caller. */
export function QuestionCreateForm() {
  const router = useRouter();
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [assessmentId, setAssessmentId] = useState("");
  const [questionText, setQuestionText] = useState("");
  const [questionType, setQuestionType] = useState<QuestionType>("MCQ");
  const [difficulty, setDifficulty] = useState<Difficulty>("Beginner");
  const [points, setPoints] = useState("1");
  const [learningObjective, setLearningObjective] = useState("");
  const [estimatedTimeMinutes, setEstimatedTimeMinutes] = useState("");
  const [options, setOptions] = useState<OptionDraft[]>([newOption(0), newOption(1)]);
  const [correctIds, setCorrectIds] = useState<Set<string>>(new Set());
  const [shortAnswerText, setShortAnswerText] = useState("");
  const [explanation, setExplanation] = useState("");

  const [submitting, setSubmitting] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { assessments: rows } = await listAssessmentsForFaculty();
        if (cancelled) return;
        setAssessments(rows);
        if (rows.length > 0) setAssessmentId(rows[0].id);
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof ApiError ? err.message : "Could not load assessments.");
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const isChoiceType = questionType === "MCQ" || questionType === "MULTIPLE_SELECT";

  function addOption() {
    setOptions((prev) => [...prev, newOption(prev.length)]);
  }

  function removeOption(id: string) {
    setOptions((prev) => prev.filter((o) => o.id !== id).map((o, i) => ({ ...o, display_order: i })));
    setCorrectIds((prev) => {
      const next = new Set(prev);
      next.delete(id);
      return next;
    });
  }

  function updateOptionText(id: string, text: string) {
    setOptions((prev) => prev.map((o) => (o.id === id ? { ...o, option_text: text } : o)));
  }

  function toggleCorrect(id: string) {
    setCorrectIds((prev) => {
      if (questionType === "MCQ") return new Set([id]);
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSubmitError(null);

    if (!assessmentId) {
      setSubmitError("Choose an assessment.");
      return;
    }
    if (isChoiceType) {
      const filled = options.filter((o) => o.option_text.trim() !== "");
      if (filled.length < 2) {
        setSubmitError("Provide at least two options.");
        return;
      }
      if (correctIds.size === 0) {
        setSubmitError("Mark at least one option as correct.");
        return;
      }
    } else if (shortAnswerText.trim() === "") {
      setSubmitError("Provide the correct answer text.");
      return;
    }
    const trimmedTime = estimatedTimeMinutes.trim();
    if (trimmedTime !== "" && (!/^\d+$/.test(trimmedTime) || Number(trimmedTime) <= 0)) {
      setSubmitError("Estimated time must be a positive whole number of minutes.");
      return;
    }

    setSubmitting(true);
    try {
      const created = await createQuestion({
        assessment_id: assessmentId,
        question_text: questionText,
        question_type: questionType,
        scoring_method: "OBJECTIVE",
        difficulty,
        points,
        learning_objective: learningObjective.trim() || null,
        estimated_time_minutes: trimmedTime === "" ? null : Number(trimmedTime),
        options: isChoiceType ? options.filter((o) => o.option_text.trim() !== "") : [],
        answer_key: isChoiceType
          ? { correct_option_ids: Array.from(correctIds) }
          : { correct_answer_text: shortAnswerText, explanation: explanation || null },
      });
      toast.success("Question created and submitted for review.");
      router.push(`/faculty/questions/${created.id}`);
    } catch (err) {
      setSubmitError(err instanceof ApiError ? err.message : "Could not create the question.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    // noValidate: every field's validation in this form is custom JS
    // (submitError, shown consistently below the fields) -- without it,
    // the browser's own native constraint validation (e.g. the
    // estimated-time input's min="1"/step="1") would silently block
    // submission and pre-empt handleSubmit before it ever runs, so the
    // custom "Estimated time must be a positive whole number of
    // minutes." message would never actually show for exactly the
    // values it exists to catch.
    <form onSubmit={handleSubmit} noValidate>
      <Card>
        <CardHeader>
          <CardTitle className="text-lg">New question</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {loadError && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertCircle className="size-3.5 shrink-0" /> {loadError}
            </p>
          )}

          <div className="space-y-1.5">
            <Label htmlFor="q-assessment">Assessment</Label>
            <Select
              value={assessmentId}
              onValueChange={(next) => setAssessmentId(next ?? "")}
              items={Object.fromEntries(assessments.map((a) => [a.id, a.title]))}
            >
              <SelectTrigger id="q-assessment" className="w-full">
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
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="q-text">Question text</Label>
            <textarea
              id="q-text"
              value={questionText}
              onChange={(e) => setQuestionText(e.target.value)}
              required
              rows={3}
              className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
            />
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-3">
            <div className="space-y-1.5">
              <Label htmlFor="q-type">Question type</Label>
              <Select
                value={questionType}
                onValueChange={(next) => setQuestionType(next as QuestionType)}
                items={QUESTION_TYPE_ITEMS}
              >
                <SelectTrigger id="q-type" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {QUESTION_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {QUESTION_TYPE_ITEMS[t]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                Code and subjective questions aren&apos;t available here yet -- there&apos;s no automatic scoring
                for them.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="q-difficulty">Difficulty</Label>
              <Select
                value={difficulty}
                onValueChange={(next) => setDifficulty(next as Difficulty)}
                items={DIFFICULTY_ITEMS}
              >
                <SelectTrigger id="q-difficulty" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {DIFFICULTIES.map((d) => (
                    <SelectItem key={d} value={d}>
                      {d}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="q-points">Points</Label>
              <Input
                id="q-points"
                type="number"
                min="0.01"
                step="0.01"
                value={points}
                onChange={(e) => setPoints(e.target.value)}
                required
              />
            </div>
          </div>

          <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="q-objective">Learning objective (optional)</Label>
              <textarea
                id="q-objective"
                value={learningObjective}
                onChange={(e) => setLearningObjective(e.target.value)}
                rows={2}
                placeholder="What should a student be able to do after this question?"
                className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="q-time">Estimated time (minutes, optional)</Label>
              <Input
                id="q-time"
                type="number"
                min="1"
                step="1"
                value={estimatedTimeMinutes}
                onChange={(e) => setEstimatedTimeMinutes(e.target.value)}
              />
            </div>
          </div>

          {isChoiceType ? (
            <div className="space-y-2">
              <Label>Options (check the correct {questionType === "MCQ" ? "one" : "ones"})</Label>
              <p className="text-xs text-muted-foreground">
                {questionType === "MCQ"
                  ? "Exactly one option must be marked correct."
                  : "Mark one or more options as correct."}
              </p>
              {options.map((option) => (
                <div key={option.id} className="flex items-center gap-2">
                  <input
                    type={questionType === "MCQ" ? "radio" : "checkbox"}
                    name="correct-option"
                    checked={correctIds.has(option.id)}
                    onChange={() => toggleCorrect(option.id)}
                    className="size-4 shrink-0 accent-primary"
                    aria-label={`Mark option ${option.display_order + 1} correct`}
                  />
                  <Input
                    value={option.option_text}
                    onChange={(e) => updateOptionText(option.id, e.target.value)}
                    placeholder={`Option ${option.display_order + 1}`}
                  />
                  <Button
                    type="button"
                    variant="outline"
                    size="sm"
                    onClick={() => removeOption(option.id)}
                    disabled={options.length <= 2}
                  >
                    <Trash2 className="size-3.5" />
                  </Button>
                </div>
              ))}
              <Button type="button" variant="outline" size="sm" onClick={addOption}>
                <Plus className="size-3.5" /> Add option
              </Button>
            </div>
          ) : (
            <div className="flex flex-col gap-4">
              <div className="space-y-1.5">
                <Label htmlFor="q-answer">Correct answer</Label>
                <Input id="q-answer" value={shortAnswerText} onChange={(e) => setShortAnswerText(e.target.value)} />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="q-explanation">Explanation (optional)</Label>
                <textarea
                  id="q-explanation"
                  value={explanation}
                  onChange={(e) => setExplanation(e.target.value)}
                  rows={2}
                  className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                />
              </div>
            </div>
          )}
        </CardContent>
        <CardFooter className="flex-col items-stretch gap-2">
          {submitError && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertCircle className="size-3.5 shrink-0" /> {submitError}
            </p>
          )}
          <Button type="submit" disabled={submitting}>
            {submitting && <Loader2 className="size-3.5 animate-spin" />}
            Save as draft
          </Button>
        </CardFooter>
      </Card>
    </form>
  );
}
