import Link from "next/link";
import { Briefcase, Building2, CheckCircle2, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { StudentOpportunitySummary } from "@/types/student-opportunity";

const TYPE_LABEL: Record<StudentOpportunitySummary["source_type"], string> = {
  JOB: "Job",
  INTERNSHIP: "Internship",
};

/** One opportunity summary, used by OpportunityListView. `href` links into
 * the route's own detail path (/student/internships/[id] or
 * /student/jobs/[id]). */
export function OpportunityCard({
  opportunity,
  href,
}: {
  opportunity: StudentOpportunitySummary;
  href: string;
}) {
  const company = opportunity.industry?.company_name;
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{TYPE_LABEL[opportunity.source_type]}</Badge>
          {opportunity.location && (
            <Badge variant="outline" className="gap-1">
              <MapPin className="size-3" aria-hidden="true" />
              {opportunity.location}
            </Badge>
          )}
          {opportunity.has_applied && (
            <Badge className="gap-1 bg-emerald-600 text-white hover:bg-emerald-600">
              <CheckCircle2 className="size-3" aria-hidden="true" />
              Applied
            </Badge>
          )}
        </div>
        <CardTitle className="text-base">{opportunity.title}</CardTitle>
        {company && (
          <p className="flex items-center gap-1 text-sm text-muted-foreground">
            <Building2 className="size-3.5" aria-hidden="true" />
            {company}
          </p>
        )}
      </CardHeader>
      <CardContent className="flex-1 text-sm text-muted-foreground">
        <p className="line-clamp-3">{opportunity.description}</p>
      </CardContent>
      <CardFooter>
        <Button className="w-full" render={<Link href={href} />} nativeButton={false}>
          <Briefcase /> View Details
        </Button>
      </CardFooter>
    </Card>
  );
}
