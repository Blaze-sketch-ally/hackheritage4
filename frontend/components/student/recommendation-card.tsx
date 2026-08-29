import { Briefcase, Clock, IndianRupee, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import type { RecommendationItem } from "@/lib/mock/student-dashboard";

export function RecommendationCard({ item }: { item: RecommendationItem }) {
  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-2">
          <div className="space-y-0.5">
            <p className="text-sm font-medium">{item.title}</p>
            <p className="text-xs text-muted-foreground">{item.organization}</p>
          </div>
          <Badge variant="outline" className="shrink-0 border-indigo-500/30 bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
            {item.matchPercent}% match
          </Badge>
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <MapPin className="size-3.5" aria-hidden="true" />
            {item.location}
          </span>
          <span className="flex items-center gap-1">
            <Briefcase className="size-3.5" aria-hidden="true" />
            {item.mode}
          </span>
          {item.duration ? (
            <span className="flex items-center gap-1">
              <Clock className="size-3.5" aria-hidden="true" />
              {item.duration}
            </span>
          ) : null}
          {item.compensation ? (
            <span className="flex items-center gap-1">
              <IndianRupee className="size-3.5" aria-hidden="true" />
              {item.compensation}
            </span>
          ) : null}
        </div>

        <Button variant="outline" size="sm" className="w-full" disabled title="Demo data — not a real listing yet">
          View Details
        </Button>
      </CardContent>
    </Card>
  );
}
