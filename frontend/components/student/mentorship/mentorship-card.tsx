import Link from "next/link";
import { ArrowRight, Building2, Clock, MapPin, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { STUDENT_MENTORSHIP_WORK_MODE_LABELS } from "@/types/student-mentorship";
import type { StudentMentorshipSummary } from "@/types/student-mentorship";

/** One mentorship-opportunity summary, used by MentorshipListView. `href`
 * links into /student/mentorship/[id]. */
export function MentorshipCard({
  mentorship,
  href,
}: {
  mentorship: StudentMentorshipSummary;
  href: string;
}) {
  const organizer = mentorship.organizer?.company_name;
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">
            {STUDENT_MENTORSHIP_WORK_MODE_LABELS[mentorship.work_mode]}
          </Badge>
          {mentorship.location && (
            <Badge variant="outline" className="gap-1">
              <MapPin className="size-3" aria-hidden="true" />
              {mentorship.location}
            </Badge>
          )}
        </div>
        <CardTitle className="text-base">{mentorship.title}</CardTitle>
        {organizer && (
          <p className="flex items-center gap-1 text-sm text-muted-foreground">
            <Building2 className="size-3.5" aria-hidden="true" />
            {organizer}
          </p>
        )}
      </CardHeader>
      <CardContent className="flex-1 space-y-2 text-sm text-muted-foreground">
        <p className="line-clamp-3">{mentorship.description}</p>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          <span className="flex items-center gap-1">
            <Clock className="size-3.5" aria-hidden="true" />
            {mentorship.duration_months} month{mentorship.duration_months === 1 ? "" : "s"}
          </span>
          <span className="flex items-center gap-1">
            <Users className="size-3.5" aria-hidden="true" />
            {mentorship.capacity} place{mentorship.capacity === 1 ? "" : "s"}
          </span>
        </div>
      </CardContent>
      <CardFooter>
        <Button
          variant="outline"
          className="w-full"
          render={<Link href={href} />}
          nativeButton={false}
        >
          View details <ArrowRight className="size-4" />
        </Button>
      </CardFooter>
    </Card>
  );
}
