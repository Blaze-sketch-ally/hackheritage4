"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, CheckCircle2, History, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { AttemptStatusBadge } from "@/components/student/assessment/attempt-status-badge";
import { ApiError } from "@/lib/api";
import { attemptDisplayStatus, getAttemptHistory } from "@/lib/student/assessment";
import type { AttemptHistoryItem } from "@/types/assessment";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; attempts: AttemptHistoryItem[] };

/** GET /api/v1/attempts -- every value shown (score, percentage, passed,
 * skill_verified) comes directly from the backend response; nothing here
 * recalculates a pass/fail or verification outcome. */
export function AssessmentHistoryView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const attempts = await getAttemptHistory();
        if (cancelled) return;
        setState({ status: "ready", attempts });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your assessment history."),
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground" aria-busy="true">
          <p className="text-sm">Loading your history…</p>
        </CardContent>
      </Card>
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <p className="font-medium">{state.error.message}</p>
          <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { attempts } = state;

  if (attempts.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
          <History className="size-8" />
          <p className="font-medium text-foreground">No assessment attempts yet</p>
          <p className="text-sm">Take an assessment to see your history here.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Skill</TableHead>
            <TableHead>Difficulty</TableHead>
            <TableHead>Date</TableHead>
            <TableHead>Score</TableHead>
            <TableHead>Percentage</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Verification</TableHead>
            <TableHead>Action</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {attempts.map((attempt) => (
            <HistoryRow key={attempt.id} attempt={attempt} />
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function HistoryRow({ attempt }: { attempt: AttemptHistoryItem }) {
  const skillName = attempt.assessment?.title ?? "Assessment no longer available";
  const difficulty = attempt.assessment?.difficulty;

  return (
    <TableRow>
      <TableCell className="font-medium">{skillName}</TableCell>
      <TableCell>{difficulty ?? "—"}</TableCell>
      <TableCell>{new Date(attempt.started_at).toLocaleDateString()}</TableCell>
      <TableCell>
        {attempt.score != null && attempt.total_marks != null ? `${attempt.score} / ${attempt.total_marks}` : "—"}
      </TableCell>
      <TableCell>{attempt.percentage != null ? `${attempt.percentage}%` : "—"}</TableCell>
      <TableCell>
        <AttemptStatusBadge status={attemptDisplayStatus(attempt)} />
      </TableCell>
      <TableCell>
        {attempt.skill_verified === true ? (
          <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="size-3.5" aria-hidden="true" /> Verified
          </span>
        ) : attempt.skill_verified === false ? (
          <span className="text-muted-foreground">Not Verified</span>
        ) : (
          "—"
        )}
      </TableCell>
      <TableCell>
        <HistoryRowAction attempt={attempt} />
      </TableCell>
    </TableRow>
  );
}

/** The only genuinely supported destination for any attempt is the
 * assessment's own taking route (/student/assessment/{assessment_id}):
 * AssessmentTakingView resumes a real IN_PROGRESS attempt there via
 * GET .../attempts/current, but there is no route or API that reconstructs
 * a COMPLETED attempt's historical result by attempt id -- so a completed
 * row links to the same place with an honest "View Assessment" label
 * (which will offer a retake), never a fabricated "View Result". No
 * action for ABANDONED (nothing to resume) or a since-deleted assessment. */
function HistoryRowAction({ attempt }: { attempt: AttemptHistoryItem }) {
  const assessmentId = attempt.assessment?.id;
  if (!assessmentId) return <span className="text-muted-foreground">—</span>;

  if (attempt.status === "IN_PROGRESS") {
    return (
      <Button
        size="sm"
        variant="outline"
        render={<Link href={`/student/assessment/${assessmentId}`} />}
        nativeButton={false}
      >
        Resume
      </Button>
    );
  }
  if (attempt.status === "COMPLETED") {
    return (
      <Button
        size="sm"
        variant="outline"
        render={<Link href={`/student/assessment/${assessmentId}`} />}
        nativeButton={false}
      >
        View Assessment
      </Button>
    );
  }
  return <span className="text-muted-foreground">—</span>;
}
