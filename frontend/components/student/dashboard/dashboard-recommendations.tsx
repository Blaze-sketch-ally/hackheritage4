"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowRight, Briefcase, GraduationCap, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getRecommendations } from "@/lib/student/recommendations";
import type { StudentRecommendationsResponse } from "@/types/student-recommendation";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; data: StudentRecommendationsResponse };

const PREVIEW_COUNT = 3;

/**
 * Compact dashboard preview of the canonical aggregate recommendation
 * surface (GET /api/v1/student/recommendations, built in S7). Shows a few
 * real recommended opportunities + learning resources and links to the
 * full /student/recommendations page. No fabricated listings, no match
 * percentages — the opportunity line is the engine's own "N of M skills"
 * count. Self-contained: its own error state never blanks the dashboard.
 */
export function DashboardRecommendations() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getRecommendations({ limit: PREVIEW_COUNT })
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch(() => {
        // Any failure (including an expired session / 401) degrades to a
        // retryable error — never leaves the card stuck on its skeleton.
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const opportunities =
    state.status === "ready" ? state.data.opportunities.slice(0, PREVIEW_COUNT) : [];
  const learning = state.status === "ready" ? state.data.learning.slice(0, PREVIEW_COUNT) : [];
  const isEmpty =
    state.status === "ready" && opportunities.length === 0 && learning.length === 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Sparkles className="size-4 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
          Recommended For You
        </CardTitle>
        <CardAction>
          <Button
            variant="ghost"
            size="sm"
            render={<Link href="/student/recommendations" />}
            nativeButton={false}
          >
            View all
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        {state.status === "loading" && (
          <div className="space-y-2" aria-hidden="true">
            {[0, 1, 2].map((i) => (
              <div key={i} className="h-12 animate-pulse rounded-lg bg-muted" />
            ))}
          </div>
        )}

        {state.status === "error" && (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <AlertCircle className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">Couldn&apos;t load your recommendations.</p>
            <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
              Try again
            </Button>
          </div>
        )}

        {isEmpty && (
          <div className="flex flex-col items-center gap-2 py-6 text-center">
            <p className="text-sm font-medium">No recommendations yet</p>
            <p className="text-xs text-muted-foreground">
              Add your skills or set a target role, then browse the full lists.
            </p>
            <div className="mt-1 flex flex-wrap justify-center gap-2">
              <Button
                variant="outline"
                size="sm"
                render={<Link href="/student/internships" />}
                nativeButton={false}
              >
                Internships
              </Button>
              <Button
                variant="outline"
                size="sm"
                render={<Link href="/student/learning" />}
                nativeButton={false}
              >
                Learning
              </Button>
            </div>
          </div>
        )}

        {state.status === "ready" && opportunities.length > 0 && (
          <div className="space-y-1.5">
            {opportunities.map((item) => (
              <Link
                key={item.id}
                href={item.detail_path}
                className="flex items-start gap-2 rounded-lg border px-2.5 py-2 text-sm transition-colors hover:bg-muted"
              >
                <Briefcase
                  className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{item.title}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {item.company ? `${item.company} · ` : ""}
                    Matches {item.matched_skill_count} of {item.required_skill_count} skills
                  </span>
                </span>
                <ArrowRight className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
              </Link>
            ))}
          </div>
        )}

        {state.status === "ready" && learning.length > 0 && (
          <div className="space-y-1.5">
            {learning.map((item) => (
              <Link
                key={item.resource.id}
                href={`/student/learning/${item.resource.id}`}
                className="flex items-start gap-2 rounded-lg border px-2.5 py-2 text-sm transition-colors hover:bg-muted"
              >
                <GraduationCap
                  className="mt-0.5 size-4 shrink-0 text-muted-foreground"
                  aria-hidden="true"
                />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-medium">{item.resource.title}</span>
                  <span className="block truncate text-xs text-muted-foreground">
                    {item.resource.provider ?? "Learning resource"}
                  </span>
                </span>
                <ArrowRight className="mt-0.5 size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />
              </Link>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
