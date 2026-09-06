import Link from "next/link";
import { ArrowRight, Building2, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { RecommendedOpportunity } from "@/types/student-recommendation";

const TYPE_LABEL: Record<RecommendedOpportunity["type"], string> = {
  INTERNSHIP: "Internship",
  JOB: "Job",
};

// The canonical match_service band, shown as a plain word — never a
// fabricated percentage or "AI confidence".
const BAND_LABEL: Record<RecommendedOpportunity["match_band"], string> = {
  STRONG: "Strong skill match",
  GOOD: "Good skill match",
  PARTIAL: "Partial skill match",
  LOW: "Some overlap",
};

export function OpportunityRecommendationCard({ item }: { item: RecommendedOpportunity }) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{TYPE_LABEL[item.type]}</Badge>
          {item.work_mode && <Badge variant="outline">{item.work_mode}</Badge>}
          {item.location && (
            <Badge variant="outline" className="gap-1">
              <MapPin className="size-3" aria-hidden="true" />
              {item.location}
            </Badge>
          )}
        </div>
        <CardTitle className="text-base">{item.title}</CardTitle>
        {item.company && (
          <p className="flex items-center gap-1 text-sm text-muted-foreground">
            <Building2 className="size-3.5" aria-hidden="true" />
            {item.company}
          </p>
        )}
      </CardHeader>
      <CardContent className="flex-1 space-y-2 text-sm text-muted-foreground">
        <p className="line-clamp-2">{item.description}</p>
        {/* Truthful, canonical explanation: a genuine count from
            match_service, not a made-up percentage. */}
        <p className="text-xs">
          <span className="font-medium text-foreground">
            Matches {item.matched_skill_count} of {item.required_skill_count} skills this role
            needs
          </span>
          {" — "}
          {BAND_LABEL[item.match_band]}
        </p>
        {item.relevant_skills.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {item.relevant_skills.slice(0, 6).map((skill) => (
              <Badge key={skill} variant="outline" className="font-normal">
                {skill}
              </Badge>
            ))}
          </div>
        )}
      </CardContent>
      <CardFooter>
        <Button
          variant="outline"
          className="w-full"
          render={<Link href={item.detail_path} />}
          nativeButton={false}
        >
          View {TYPE_LABEL[item.type].toLowerCase()} <ArrowRight className="size-4" />
        </Button>
      </CardFooter>
    </Card>
  );
}
