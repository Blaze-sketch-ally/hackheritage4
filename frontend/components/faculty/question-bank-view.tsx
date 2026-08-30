"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, Check, Loader2, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { approveQuestion, listMyQuestions, rejectQuestion } from "@/lib/faculty/question-bank";
import type { QuestionBank, ReviewStatus } from "@/types/question-bank";

/** Faculty's own question bank: their own questions (any review status)
 * plus every other setter's PENDING question, for review -- exactly what
 * the backend's RLS-scoped list endpoint returns. Approve/reject act
 * directly on this list; the backend rejects (403) an attempt to review
 * one's own question, so that action is simply never shown for a
 * caller's own rows. */
type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; questions: QuestionBank[] };

export function QuestionBankView() {
  const { user } = useAuth();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const questions = await listMyQuestions();
        if (cancelled) return;
        setState({ status: "ready", questions });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load questions.",
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function retry() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function handleReview(questionId: string, action: "approve" | "reject") {
    setActioningId(questionId);
    setActionError(null);
    try {
      const updated = action === "approve" ? await approveQuestion(questionId) : await rejectQuestion(questionId);
      setState((prev) =>
        prev.status === "ready"
          ? { ...prev, questions: prev.questions.map((q) => (q.id === questionId ? updated : q)) }
          : prev,
      );
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not update the question.");
    } finally {
      setActioningId(null);
    }
  }

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading questions…
        </CardContent>
      </Card>
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <p className="font-medium">{state.message}</p>
          <Button size="sm" onClick={retry}>
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { questions } = state;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex items-center justify-between">
        <p className="text-sm text-muted-foreground">
          Your own drafts and submissions, plus questions from other setters awaiting review.
        </p>
        <Button size="sm" render={<Link href="/faculty/questions/new" />} nativeButton={false}>
          <Plus className="size-3.5" /> New question
        </Button>
      </div>

      {actionError && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="size-3.5 shrink-0" /> {actionError}
        </p>
      )}

      {questions.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No questions yet. Create the first one for a skill assessment.
          </CardContent>
        </Card>
      ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Question</TableHead>
                <TableHead>Difficulty</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Setter</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {questions.map((q) => {
                const isOwn = q.created_by === user?.id;
                const busy = actioningId === q.id;
                return (
                  <TableRow key={q.id}>
                    <TableCell className="max-w-xs">
                      <Link href={`/faculty/questions/${q.id}`} className="line-clamp-2 hover:underline">
                        {q.question_text}
                      </Link>
                    </TableCell>
                    <TableCell>{q.difficulty}</TableCell>
                    <TableCell>
                      <ReviewStatusBadge status={q.review_status} isActive={q.is_active} />
                    </TableCell>
                    <TableCell className="text-muted-foreground">{isOwn ? "You" : "Other setter"}</TableCell>
                    <TableCell className="text-right">
                      {q.review_status === "PENDING" && !isOwn ? (
                        <div className="flex justify-end gap-1.5">
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => void handleReview(q.id, "approve")}
                          >
                            <Check className="size-3.5" /> Approve
                          </Button>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => void handleReview(q.id, "reject")}
                          >
                            <X className="size-3.5" /> Reject
                          </Button>
                        </div>
                      ) : (
                        <span className="text-xs text-muted-foreground">
                          {q.review_status === "PENDING" ? "Awaiting another setter" : "—"}
                        </span>
                      )}
                    </TableCell>
                  </TableRow>
                );
              })}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

function ReviewStatusBadge({ status, isActive }: { status: ReviewStatus; isActive: boolean }) {
  if (!isActive) return <Badge variant="secondary">Inactive</Badge>;
  if (status === "APPROVED") {
    return (
      <Badge className="bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500">Approved</Badge>
    );
  }
  if (status === "REJECTED") return <Badge variant="destructive">Rejected</Badge>;
  return <Badge variant="outline">Pending</Badge>;
}
