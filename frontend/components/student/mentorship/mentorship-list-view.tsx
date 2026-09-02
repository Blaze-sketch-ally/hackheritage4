"use client";

import { useEffect, useState } from "react";
import { Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { ErrorState } from "@/components/common/error-state";
import { MentorshipCard } from "@/components/student/mentorship/mentorship-card";
import { ApiError } from "@/lib/api";
import { listMentorships } from "@/lib/student/mentorship";
import {
  STUDENT_MENTORSHIP_WORK_MODES,
  STUDENT_MENTORSHIP_WORK_MODE_LABELS,
} from "@/types/student-mentorship";
import type {
  StudentMentorshipSummary,
  StudentMentorshipWorkMode,
} from "@/types/student-mentorship";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; mentorships: StudentMentorshipSummary[] };

/** GET /api/v1/student/mentorship via the FastAPI bridge. Work-mode
 * filter is applied server-side (a small fixed enum); the title search is
 * applied client-side over what came back, mirroring OpportunityListView /
 * EventsListView. */
export function MentorshipListView() {
  const [workMode, setWorkMode] = useState<StudentMentorshipWorkMode | null>(null);
  const [search, setSearch] = useState("");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listMentorships(workMode ? { workMode } : undefined)
      .then(({ mentorship_opportunities }) => {
        if (!cancelled) setState({ status: "ready", mentorships: mentorship_opportunities });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            status: "error",
            message:
              err instanceof ApiError ? err.message : "Could not load mentorship opportunities.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [workMode, reloadKey]);

  const visible =
    state.status === "ready"
      ? state.mentorships.filter((m) =>
          search.trim() ? m.title.toLowerCase().includes(search.trim().toLowerCase()) : true,
        )
      : [];

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap items-center gap-2">
        <Input
          type="search"
          aria-label="Search mentorship opportunities"
          placeholder="Search by title..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="max-w-xs"
        />
        <div className="flex flex-wrap gap-1.5">
          <Button
            variant={workMode === null ? "default" : "outline"}
            size="sm"
            onClick={() => setWorkMode(null)}
          >
            All
          </Button>
          {STUDENT_MENTORSHIP_WORK_MODES.map((mode) => (
            <Button
              key={mode}
              variant={workMode === mode ? "default" : "outline"}
              size="sm"
              onClick={() => setWorkMode(mode)}
            >
              {STUDENT_MENTORSHIP_WORK_MODE_LABELS[mode]}
            </Button>
          ))}
        </div>
      </div>

      {state.status === "loading" && <MentorshipListSkeleton />}

      {state.status === "error" && (
        <ErrorState
          message={state.message}
          onRetry={() => {
            setState({ status: "loading" });
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {state.status === "ready" && visible.length === 0 && (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
            <Users className="size-8" aria-hidden="true" />
            <p className="font-medium text-foreground">
              {state.mentorships.length === 0
                ? "No mentorship opportunities yet."
                : `No opportunities match "${search.trim()}".`}
            </p>
            <p className="text-sm">
              Mentorship opportunities are published by industry partners — check back later.
            </p>
          </CardContent>
        </Card>
      )}

      {state.status === "ready" && visible.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visible.map((mentorship) => (
            <MentorshipCard
              key={mentorship.id}
              mentorship={mentorship}
              href={`/student/mentorship/${mentorship.id}`}
            />
          ))}
        </div>
      )}
    </div>
  );
}

function MentorshipListSkeleton() {
  return (
    <div
      className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3"
      aria-busy="true"
      aria-label="Loading mentorship opportunities"
    >
      {[0, 1, 2].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2 py-4">
            <div className="h-4 w-16 rounded bg-muted" />
            <div className="h-5 w-3/4 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
