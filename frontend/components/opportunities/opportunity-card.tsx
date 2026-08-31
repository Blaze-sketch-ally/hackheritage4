import Link from "next/link";
import { Briefcase, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import type { Opportunity } from "@/types/opportunity";

const TYPE_LABEL: Record<Opportunity["opportunity_type"], string> = {
  JOB: "Job",
  INTERNSHIP: "Internship",
};

/** One opportunity summary, used by OpportunityListView -- shared by
 * /student/opportunities, /student/jobs, and /student/internships (no
 * separate card component per type). `href` lets each route link into
 * its own detail path (/student/opportunities/[id] vs
 * /student/jobs/[id] vs /student/internships/[id] all render the same
 * OpportunityDetailView, just reached via different URLs). */
export function OpportunityCard({ opportunity, href }: { opportunity: Opportunity; href: string }) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{TYPE_LABEL[opportunity.opportunity_type]}</Badge>
          {opportunity.location && (
            <Badge variant="outline" className="gap-1">
              <MapPin className="size-3" aria-hidden="true" />
              {opportunity.location}
            </Badge>
          )}
        </div>
        <CardTitle className="text-base">{opportunity.title}</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 text-sm text-muted-foreground">
        {opportunity.description && <p className="line-clamp-3">{opportunity.description}</p>}
      </CardContent>
      <CardFooter>
        <Button className="w-full" render={<Link href={href} />} nativeButton={false}>
          <Briefcase /> View Details
        </Button>
      </CardFooter>
    </Card>
  );
}
