"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Check, Loader2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { approveQuestion, getQuestion, rejectQuestion, updateQuestion } from "@/lib/faculty/question-bank";
import type { QuestionBank } from "@/types/question-bank";

/** One question's faculty-facing detail: full content (including the
 * answer key -- never shown to students), edit access to the caller's
 * own non-approved fields, and approve/reject for someone else's PENDING
 * submission. All permission boundaries here are cosmetic convenience
 * (hiding actions that would 403 anyway) -- RLS + the
 * prevent_unauthorized_question_review trigger are the real enforcement,
 * confirmed by the backend rejecting anything this UI might get wrong. */
export function QuestionDetailView({ questionId }: { questionId: string }) {
  const { user } = useAuth();
  const [question, setQuestion] = useState<QuestionBank | null>(null);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  const [editing, setEditing] = useState(false);
  const [draftText, setDraftText] = useState("");
  const [draftPoints, setDraftPoints] = useState("");
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [reviewing, setReviewing] = useState(false);
  const [reviewError, setReviewError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const data = await getQuestion(questionId);
        if (cancelled) return;
        setQuestion(data);
        setDraftText(data.question_text);
        setDraftPoints(data.points);
        setLoading(false);
      } catch (err) {
        if (cancelled) return;
        setLoadError(
          err instanceof ApiError && err.status === 404
            ? "This question doesn't exist or you don't have access to it."
            : err instanceof ApiError
              ? err.message
              : "Could not load the question.",
        );
        setLoading(false);
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [questionId, reloadKey]);

  function retry() {
    setLoading(true);
    setLoadError(null);
    setReloadKey((k) => k + 1);
  }

  async function handleSaveEdit() {
    setSaving(true);
    setSaveError(null);
    try {
      const updated = await updateQuestion(questionId, {
        question_text: draftText,
        points: draftPoints,
      });
      setQuestion(updated);
      setEditing(false);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Could not save changes.");
    } finally {
      setSaving(false);
    }
  }

  async function handleResubmit() {
    setSaving(true);
    setSaveError(null);
    try {
      // review_status: "PENDING" is the only value this endpoint accepts
      // (422 otherwise) -- the trigger allows a question's own creator to
      // move it back to PENDING after revising it, never to
      // APPROVED/REJECTED directly.
      const updated = await updateQuestion(questionId, {
        question_text: draftText,
        points: draftPoints,
        review_status: "PENDING",
      });
      setQuestion(updated);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Could not resubmit the question.");
    } finally {
      setSaving(false);
    }
  }

  async function handleReview(action: "approve" | "reject") {
    setReviewing(true);
    setReviewError(null);
    try {
      const updated = action === "approve" ? await approveQuestion(questionId) : await rejectQuestion(questionId);
      setQuestion(updated);
    } catch (err) {
      setReviewError(err instanceof ApiError ? err.message : "Could not update the question.");
    } finally {
      setReviewing(false);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading…
        </CardContent>
      </Card>
    );
  }

  if (loadError || !question) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <p className="font-medium">{loadError}</p>
          <div className="flex gap-2">
            {loadError && !loadError.includes("don't have access") && (
              <Button size="sm" onClick={retry}>
                Try again
              </Button>
            )}
            <Button variant="outline" size="sm" render={<Link href="/faculty/questions" />} nativeButton={false}>
              <ArrowLeft className="size-3.5" /> Back to question bank
            </Button>
          </div>
        </CardContent>
      </Card>
    );
  }

  const isOwn = question.created_by === user?.id;
  const isApproved = question.review_status === "APPROVED";
  const canEdit = isOwn && !isApproved;
  const canReview = !isOwn && question.review_status === "PENDING";

  return (
    <div className="flex flex-col gap-4">
      <Button variant="outline" size="sm" render={<Link href="/faculty/questions" />} nativeButton={false} className="self-start">
        <ArrowLeft className="size-3.5" /> Back to question bank
      </Button>

      <Card>
        <CardHeader>
          <div className="flex items-start justify-between gap-3">
            <CardTitle className="text-lg">Question detail</CardTitle>
            <div className="flex gap-2">
              <Badge variant="outline">{question.difficulty}</Badge>
              <Badge variant={question.review_status === "APPROVED" ? "default" : "outline"}>
                {question.review_status}
              </Badge>
              {!question.is_active && <Badge variant="secondary">Inactive</Badge>}
            </div>
          </div>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          {editing ? (
            <div className="flex flex-col gap-3">
              <div className="space-y-1.5">
                <Label htmlFor="edit-text">Question text</Label>
                <textarea
                  id="edit-text"
                  value={draftText}
                  onChange={(e) => setDraftText(e.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-input bg-transparent px-2.5 py-1.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50"
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor="edit-points">Points</Label>
                <Input id="edit-points" value={draftPoints} onChange={(e) => setDraftPoints(e.target.value)} />
              </div>
            </div>
          ) : (
            <div>
              <p className="text-base">{question.question_text}</p>
              <p className="mt-1 text-sm text-muted-foreground">{question.points} pts</p>
            </div>
          )}

          {question.options.length > 0 && (
            <ul className="flex flex-col gap-1.5">
              {question.options.map((option) => {
                const isCorrect = question.answer_key?.correct_option_ids?.includes(option.id) ?? false;
                return (
                  <li
                    key={option.id}
                    className={`rounded-lg border px-3 py-2 text-sm ${isCorrect ? "border-emerald-500/40 bg-emerald-500/10" : "border-border"}`}
                  >
                    {option.option_text} {isCorrect && <span className="text-xs text-emerald-600 dark:text-emerald-400">(correct)</span>}
                  </li>
                );
              })}
            </ul>
          )}

          {question.answer_key?.correct_answer_text && (
            <p className="text-sm">
              <span className="text-muted-foreground">Correct answer: </span>
              {question.answer_key.correct_answer_text}
            </p>
          )}

          {saveError && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertCircle className="size-3.5 shrink-0" /> {saveError}
            </p>
          )}
        </CardContent>
        {canEdit && (
          <CardFooter className="gap-2">
            {editing ? (
              <>
                <Button size="sm" onClick={handleSaveEdit} disabled={saving}>
                  {saving && <Loader2 className="size-3.5 animate-spin" />} Save
                </Button>
                <Button size="sm" variant="outline" onClick={() => setEditing(false)} disabled={saving}>
                  Cancel
                </Button>
              </>
            ) : (
              <Button size="sm" variant="outline" onClick={() => setEditing(true)}>
                Edit
              </Button>
            )}
            {question.review_status === "REJECTED" && !editing && (
              <Button size="sm" onClick={handleResubmit} disabled={saving}>
                Resubmit for review
              </Button>
            )}
          </CardFooter>
        )}
        {canReview && (
          <CardFooter className="flex-col items-stretch gap-2">
            {reviewError && (
              <p className="flex items-center gap-1.5 text-sm text-destructive">
                <AlertCircle className="size-3.5 shrink-0" /> {reviewError}
              </p>
            )}
            <div className="flex gap-2">
              <Button size="sm" onClick={() => void handleReview("approve")} disabled={reviewing}>
                <Check className="size-3.5" /> Approve
              </Button>
              <Button size="sm" variant="outline" onClick={() => void handleReview("reject")} disabled={reviewing}>
                <X className="size-3.5" /> Reject
              </Button>
            </div>
          </CardFooter>
        )}
      </Card>
    </div>
  );
}
