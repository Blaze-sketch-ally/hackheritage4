"use client";

import Link from "next/link";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/common/empty-state";
import type { Priority, Recommendation } from "@/types/skill-gap";

const PRIORITY_GROUPS: { priority: Priority; heading: string; className: string }[] = [
  { priority: "HIGH", heading: "High Priority", className: "border-destructive/30 bg-destructive/10 text-destructive" },
  {
    priority: "MEDIUM",
    heading: "Medium Priority",
    className: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
  },
  { priority: "LOW", heading: "Low Priority", className: "border-border text-muted-foreground" },
];

/** Recommendations returned by the backend recommendation engine --
 * `reason` is server-authored text, grouped here by the server-computed
 * `priority`. Used for both job-role-mode ("what does this role still
 * need") and personal-mode ("what should I learn next") recommendations,
 * since both share the same Recommendation shape. */
export function RecommendationsPanel({ recommendations }: { recommendations: Recommendation[] }) {
  if (recommendations.length === 0) {
    return <EmptyState title="No skill recommendations available yet." />;
  }

  return (
    <div className="space-y-5">
      {PRIORITY_GROUPS.map((group) => {
        const items = recommendations.filter((rec) => rec.priority === group.priority);
        if (items.length === 0) return null;
        return (
          <div key={group.priority} className="space-y-2">
            <div className="flex items-center gap-2">
              <h3 className="text-sm font-semibold">{group.heading}</h3>
              <Badge variant="outline" className={group.className}>
                {items.length}
              </Badge>
            </div>
            <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {items.map((rec) => (
                <RecommendationCard key={rec.skill_id} recommendation={rec} />
              ))}
            </div>
          </div>
        );
      })}
    </div>
  );
}

function RecommendationCard({ recommendation }: { recommendation: Recommendation }) {
  return (
    <Card>
      <CardContent className="space-y-2">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium">{recommendation.skill_name}</p>
          {recommendation.relationship_type ? (
            <Badge variant="secondary">{recommendation.relationship_type}</Badge>
          ) : null}
        </div>
        <p className="text-xs text-muted-foreground">{recommendation.reason}</p>
        {(recommendation.current_level || recommendation.target_level) && (
          <p className="text-xs text-muted-foreground">
            {recommendation.current_level ?? "Not Added"}
            {recommendation.target_level ? ` → ${recommendation.target_level}` : ""}
          </p>
        )}
        {recommendation.assessment_available && recommendation.assessment_id ? (
          <Button
            size="sm"
            className="w-full"
            render={<Link href={`/student/assessment/${recommendation.assessment_id}`} />}
            nativeButton={false}
          >
            Take Assessment
          </Button>
        ) : (
          <p className="text-xs text-muted-foreground">Assessment not available yet.</p>
        )}
      </CardContent>
    </Card>
  );
}
