"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertCircle, Check, Loader2, Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useAuth } from "@/hooks/use-auth";
import { ApiError } from "@/lib/api";
import { approveQuestion, listMyQuestions, rejectQuestion } from "@/lib/faculty/question-bank";
import type { Difficulty, QuestionType } from "@/types/assessment";
import type { QuestionBank, ReviewStatus } from "@/types/question-bank";

/** Phase F6.5: client-side only -- filters/sorts the already-loaded
 * question list, no new API calls per keystroke/selection. The audit
 * specifically recommended this over any new backend search endpoint
 * (no evidence question-bank size makes client-side filtering
 * impractical). */
const TYPE_FILTERS: ("ALL" | QuestionType)[] = ["ALL", "MCQ", "MULTIPLE_SELECT", "SHORT_ANSWER"];
const TYPE_FILTER_ITEMS: Record<"ALL" | QuestionType, string> = {
  ALL: "All types",
  MCQ: "Multiple choice",
  MULTIPLE_SELECT: "Multiple select",
  SHORT_ANSWER: "Short answer",
  CODE: "Code",
  SUBJECTIVE: "Subjective",
};

const STATUS_FILTERS: ("ALL" | ReviewStatus)[] = ["ALL", "PENDING", "APPROVED", "REJECTED"];
const STATUS_FILTER_ITEMS: Record<"ALL" | ReviewStatus, string> = {
  ALL: "All statuses",
  PENDING: "Pending",
  APPROVED: "Approved",
  REJECTED: "Rejected",
};

const DIFFICULTIES: Difficulty[] = ["Beginner", "Intermediate", "Advanced", "Expert"];
const DIFFICULTY_FILTERS: ("ALL" | Difficulty)[] = ["ALL", ...DIFFICULTIES];
const DIFFICULTY_FILTER_ITEMS: Record<"ALL" | Difficulty, string> = {
  ALL: "All difficulties",
  Beginner: "Beginner",
  Intermediate: "Intermediate",
  Advanced: "Advanced",
  Expert: "Expert",
};

type SortOption = "newest" | "oldest" | "points" | "difficulty" | "estimated_time";
const SORT_ITEMS: Record<SortOption, string> = {
  newest: "Newest first",
  oldest: "Oldest first",
  points: "Points (high to low)",
  difficulty: "Difficulty (low to high)",
  estimated_time: "Estimated time (short to long)",
};

function matchesSearch(question: QuestionBank, query: string): boolean {
  const needle = query.trim().toLowerCase();
  if (needle === "") return true;
  return (
    question.question_text.toLowerCase().includes(needle) ||
    question.question_type.toLowerCase().includes(needle) ||
    (question.learning_objective?.toLowerCase().includes(needle) ?? false)
  );
}

function sortQuestions(questions: QuestionBank[], sortBy: SortOption): QuestionBank[] {
  const sorted = [...questions];
  switch (sortBy) {
    case "newest":
      return sorted.sort((a, b) => b.created_at.localeCompare(a.created_at));
    case "oldest":
      return sorted.sort((a, b) => a.created_at.localeCompare(b.created_at));
    case "points":
      return sorted.sort((a, b) => Number(b.points) - Number(a.points));
    case "difficulty":
      return sorted.sort((a, b) => DIFFICULTIES.indexOf(a.difficulty) - DIFFICULTIES.indexOf(b.difficulty));
    case "estimated_time":
      return sorted.sort((a, b) => {
        // Questions with no estimated time sort last, regardless of direction.
        if (a.estimated_time_minutes == null) return b.estimated_time_minutes == null ? 0 : 1;
        if (b.estimated_time_minutes == null) return -1;
        return a.estimated_time_minutes - b.estimated_time_minutes;
      });
  }
}

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

  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<"ALL" | QuestionType>("ALL");
  const [statusFilter, setStatusFilter] = useState<"ALL" | ReviewStatus>("ALL");
  const [difficultyFilter, setDifficultyFilter] = useState<"ALL" | Difficulty>("ALL");
  const [sortBy, setSortBy] = useState<SortOption>("newest");

  function resetFilters() {
    setSearch("");
    setTypeFilter("ALL");
    setStatusFilter("ALL");
    setDifficultyFilter("ALL");
  }

  const hasActiveFilters =
    search.trim() !== "" || typeFilter !== "ALL" || statusFilter !== "ALL" || difficultyFilter !== "ALL";

  // Hooks must run unconditionally on every render (loading/error/ready
  // alike), so this is computed here, BEFORE the loading/error early
  // returns below, rather than after them -- feeding it an empty array
  // whenever state isn't "ready" yet.
  const loadedQuestions = useMemo(() => (state.status === "ready" ? state.questions : []), [state]);
  const visibleQuestions = useMemo(() => {
    const filtered = loadedQuestions.filter(
      (q) =>
        matchesSearch(q, search) &&
        (typeFilter === "ALL" || q.question_type === typeFilter) &&
        (statusFilter === "ALL" || q.review_status === statusFilter) &&
        (difficultyFilter === "ALL" || q.difficulty === difficultyFilter),
    );
    return sortQuestions(filtered, sortBy);
  }, [loadedQuestions, search, typeFilter, statusFilter, difficultyFilter, sortBy]);

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

  const questions = loadedQuestions;

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
        <>
          <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search question text, type, or learning objective…"
              className="sm:max-w-xs"
              aria-label="Search questions"
            />
            <Select value={typeFilter} onValueChange={(next) => setTypeFilter((next as typeof typeFilter) ?? "ALL")} items={TYPE_FILTER_ITEMS}>
              <SelectTrigger aria-label="Filter by question type" className="w-full sm:w-auto">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {TYPE_FILTERS.map((t) => (
                  <SelectItem key={t} value={t}>
                    {TYPE_FILTER_ITEMS[t]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={statusFilter}
              onValueChange={(next) => setStatusFilter((next as typeof statusFilter) ?? "ALL")}
              items={STATUS_FILTER_ITEMS}
            >
              <SelectTrigger aria-label="Filter by status" className="w-full sm:w-auto">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {STATUS_FILTERS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {STATUS_FILTER_ITEMS[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={difficultyFilter}
              onValueChange={(next) => setDifficultyFilter((next as typeof difficultyFilter) ?? "ALL")}
              items={DIFFICULTY_FILTER_ITEMS}
            >
              <SelectTrigger aria-label="Filter by difficulty" className="w-full sm:w-auto">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {DIFFICULTY_FILTERS.map((d) => (
                  <SelectItem key={d} value={d}>
                    {DIFFICULTY_FILTER_ITEMS[d]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select value={sortBy} onValueChange={(next) => setSortBy((next as SortOption) ?? "newest")} items={SORT_ITEMS}>
              <SelectTrigger aria-label="Sort questions" className="w-full sm:w-auto">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {(Object.keys(SORT_ITEMS) as SortOption[]).map((s) => (
                  <SelectItem key={s} value={s}>
                    {SORT_ITEMS[s]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {hasActiveFilters && (
              <Button size="sm" variant="outline" onClick={resetFilters}>
                Reset filters
              </Button>
            )}
          </div>

          {visibleQuestions.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center text-sm text-muted-foreground">
                <p>No questions match your search or filters.</p>
                <Button size="sm" variant="outline" onClick={resetFilters}>
                  Reset filters
                </Button>
              </CardContent>
            </Card>
          ) : (
        <Card>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Question</TableHead>
                <TableHead>Type</TableHead>
                <TableHead>Difficulty</TableHead>
                <TableHead>Status</TableHead>
                <TableHead>Setter</TableHead>
                <TableHead className="text-right">Actions</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {visibleQuestions.map((q) => {
                const isOwn = q.created_by === user?.id;
                const busy = actioningId === q.id;
                return (
                  <TableRow key={q.id}>
                    <TableCell className="max-w-xs">
                      <Link href={`/faculty/questions/${q.id}`} className="line-clamp-2 hover:underline">
                        {q.question_text}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{TYPE_FILTER_ITEMS[q.question_type]}</Badge>
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
        </>
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
