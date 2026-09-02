"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { BookOpen, Briefcase, Sparkles, Target, TrendingUp } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ErrorState } from "@/components/common/error-state";
import { LearningRecommendationCard } from "@/components/student/recommendations/learning-recommendation-card";
import { OpportunityRecommendationCard } from "@/components/student/recommendations/opportunity-recommendation-card";
import { ApiError } from "@/lib/api";
import { getRecommendations } from "@/lib/student/recommendations";
import type { StudentRecommendationsResponse } from "@/types/student-recommendation";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: StudentRecommendationsResponse };

const MODE_SUBTITLE: Record<StudentRecommendationsResponse["mode"], string> = {
  JOB_ROLE: "Based on the skills your saved target role needs from you.",
  PERSONAL: "Based on your current skills and Skill Gap analysis.",
};

export function RecommendationsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getRecommendations()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: err instanceof ApiError ? err.message : "Could not load your recommendations.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (state.status === "loading") return <RecommendationsSkeleton />;

  if (state.status === "error") {
    return (
      <ErrorState
        message={state.message}
        onRetry={() => {
          setState({ status: "loading" });
          setReloadKey((k) => k + 1);
        }}
      />
    );
  }

  const { data } = state;

  return (
    <div className="flex flex-col gap-8">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          {data.mode === "JOB_ROLE" ? (
            <Target className="size-4" aria-hidden="true" />
          ) : (
            <Sparkles className="size-4" aria-hidden="true" />
          )}
          {data.mode === "JOB_ROLE" && data.target_role
            ? `Target role: ${data.target_role.name}. ${MODE_SUBTITLE.JOB_ROLE}`
            : MODE_SUBTITLE[data.mode]}
        </p>
        <Button
          variant="ghost"
          size="sm"
          render={<Link href="/student/skill-gap" />}
          nativeButton={false}
        >
          <TrendingUp className="size-3.5" /> View your Skill Gap
        </Button>
      </div>

      <section aria-labelledby="rec-opportunities-heading" className="flex flex-col gap-3">
        <h2
          id="rec-opportunities-heading"
          className="flex items-center gap-2 text-base font-semibold"
        >
          <Briefcase className="size-4 text-muted-foreground" aria-hidden="true" />
          Recommended opportunities
        </h2>
        {data.opportunities.length === 0 ? (
          <EmptySection
            message="No recommended opportunities yet."
            hint="When published internships or jobs share skills with your profile, they'll appear here. Browse the full lists in the meantime."
            links={[
              { href: "/student/internships", label: "Browse internships" },
              { href: "/student/jobs", label: "Browse jobs" },
            ]}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.opportunities.map((item) => (
              <OpportunityRecommendationCard key={item.id} item={item} />
            ))}
          </div>
        )}
      </section>

      <section aria-labelledby="rec-learning-heading" className="flex flex-col gap-3">
        <h2 id="rec-learning-heading" className="flex items-center gap-2 text-base font-semibold">
          <BookOpen className="size-4 text-muted-foreground" aria-hidden="true" />
          Recommended learning
        </h2>
        {data.learning.length === 0 ? (
          <EmptySection
            message="No recommended learning resources yet."
            hint="Learning resources mapped to the skills in your Skill Gap will show up here."
            links={[{ href: "/student/learning", label: "Browse the catalog" }]}
          />
        ) : (
          <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
            {data.learning.map((item) => (
              <LearningRecommendationCard key={item.resource.id} item={item} />
            ))}
          </div>
        )}
      </section>
    </div>
  );
}

function EmptySection({
  message,
  hint,
  links,
}: {
  message: string;
  hint: string;
  links: { href: string; label: string }[];
}) {
  return (
    <Card>
      <CardContent className="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
        <p className="font-medium text-foreground">{message}</p>
        <p className="text-sm">{hint}</p>
        <div className="mt-1 flex flex-wrap justify-center gap-2">
          {links.map((link) => (
            <Button
              key={link.href}
              variant="outline"
              size="sm"
              render={<Link href={link.href} />}
              nativeButton={false}
            >
              {link.label}
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

function RecommendationsSkeleton() {
  return (
    <div className="flex flex-col gap-6" aria-busy="true" aria-label="Loading recommendations">
      {[0, 1].map((section) => (
        <div key={section} className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
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
      ))}
    </div>
  );
}
