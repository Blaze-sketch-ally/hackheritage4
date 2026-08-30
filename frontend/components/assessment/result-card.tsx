import { CheckCircle2, MinusCircle, XCircle } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";
import { isUnansweredResult } from "@/lib/student/assessment";
import type { AssessmentResultQuestion } from "@/types/assessment";

interface ResultCardProps {
  result: AssessmentResultQuestion;
  questionNumber: number;
}

/** Renders one question's full post-completion breakdown: the question,
 * the student's own answer (or "Not answered" for the Phase 1H
 * unanswered-placeholder row), the correct answer, and the awarded
 * marks/correctness -- all read directly from the backend's
 * AssessmentResultQuestion, never recomputed. This component has no way
 * to construct this data itself; it only ever renders what
 * GET /attempts/{id}/result already returned for a COMPLETED attempt. */
export function ResultCard({ result, questionNumber }: ResultCardProps) {
  const { question, student_answer, answer_key } = result;
  const unanswered = isUnansweredResult(result);
  const isCorrect = student_answer?.is_correct ?? false;
  const selectedIds = new Set(student_answer?.selected_option_ids ?? []);
  const correctIds = new Set(answer_key.correct_option_ids ?? []);

  return (
    <Card>
      <CardHeader>
        <div className="flex items-start justify-between gap-3">
          <CardTitle className="text-base leading-relaxed font-medium">
            <span className="text-muted-foreground">Q{questionNumber}.</span> {question.question_text}
          </CardTitle>
          <div className="flex shrink-0 items-center gap-2">
            <Badge variant="outline">
              {student_answer?.awarded_marks ?? "0"} / {question.points} pts
            </Badge>
            <ResultStatusBadge unanswered={unanswered} isCorrect={isCorrect} />
          </div>
        </div>
      </CardHeader>
      <CardContent className="flex flex-col gap-3">
        {(question.question_type === "MCQ" || question.question_type === "MULTIPLE_SELECT") && (
          <ul className="flex flex-col gap-1.5">
            {question.options.map((option) => {
              const wasSelected = selectedIds.has(option.id);
              const isCorrectOption = correctIds.has(option.id);
              return (
                <li
                  key={option.id}
                  className={cn(
                    "flex items-center gap-2 rounded-lg border px-3 py-2 text-sm",
                    isCorrectOption && "border-emerald-500/40 bg-emerald-500/10",
                    wasSelected && !isCorrectOption && "border-destructive/40 bg-destructive/10",
                    !wasSelected && !isCorrectOption && "border-border",
                  )}
                >
                  {isCorrectOption ? (
                    <CheckCircle2 className="size-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                  ) : wasSelected ? (
                    <XCircle className="size-4 shrink-0 text-destructive" />
                  ) : (
                    <span className="size-4 shrink-0" />
                  )}
                  <span className="flex-1">{option.option_text}</span>
                  {wasSelected && <span className="text-xs text-muted-foreground">Your answer</span>}
                </li>
              );
            })}
          </ul>
        )}

        {question.question_type === "SHORT_ANSWER" && (
          <div className="flex flex-col gap-2 text-sm">
            <div>
              <span className="text-muted-foreground">Your answer: </span>
              {unanswered ? (
                <span className="italic text-muted-foreground">Not answered</span>
              ) : (
                <span>{student_answer?.answer_text}</span>
              )}
            </div>
            {answer_key.correct_answer_text && (
              <div>
                <span className="text-muted-foreground">Correct answer: </span>
                <span className="font-medium">{answer_key.correct_answer_text}</span>
              </div>
            )}
          </div>
        )}

        {unanswered && question.question_type !== "SHORT_ANSWER" && (
          <p className="text-sm italic text-muted-foreground">Not answered</p>
        )}

        {answer_key.explanation && (
          <p className="rounded-lg bg-muted px-3 py-2 text-sm text-muted-foreground">
            {answer_key.explanation}
          </p>
        )}
      </CardContent>
    </Card>
  );
}

function ResultStatusBadge({ unanswered, isCorrect }: { unanswered: boolean; isCorrect: boolean }) {
  if (unanswered) {
    return (
      <Badge variant="secondary" className="gap-1">
        <MinusCircle className="size-3" /> Not answered
      </Badge>
    );
  }
  if (isCorrect) {
    return (
      <Badge className="gap-1 bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500">
        <CheckCircle2 className="size-3" /> Correct
      </Badge>
    );
  }
  return (
    <Badge variant="destructive" className="gap-1">
      <XCircle className="size-3" /> Incorrect
    </Badge>
  );
}
