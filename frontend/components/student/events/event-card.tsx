import Link from "next/link";
import { ArrowRight, Building2, CalendarDays, Clock, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { STUDENT_EVENT_WORK_MODE_LABELS } from "@/types/student-event";
import type { StudentEventSummary } from "@/types/student-event";

/** One event summary, used by EventsListView. `href` links into
 * /student/events/[id]. */
export function EventCard({ event, href }: { event: StudentEventSummary; href: string }) {
  const organizer = event.organizer?.company_name;
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          {event.work_mode && (
            <Badge variant="secondary">{STUDENT_EVENT_WORK_MODE_LABELS[event.work_mode]}</Badge>
          )}
          {event.location && (
            <Badge variant="outline" className="gap-1">
              <MapPin className="size-3" aria-hidden="true" />
              {event.location}
            </Badge>
          )}
        </div>
        <CardTitle className="text-base">{event.title}</CardTitle>
        {organizer && (
          <p className="flex items-center gap-1 text-sm text-muted-foreground">
            <Building2 className="size-3.5" aria-hidden="true" />
            {organizer}
          </p>
        )}
      </CardHeader>
      <CardContent className="flex-1 space-y-2 text-sm text-muted-foreground">
        <p className="line-clamp-3">{event.description}</p>
        <div className="flex flex-wrap gap-x-4 gap-y-1">
          {event.start_date && (
            <span className="flex items-center gap-1">
              <CalendarDays className="size-3.5" aria-hidden="true" />
              {new Date(event.start_date).toLocaleDateString()}
            </span>
          )}
          {event.duration_days != null && (
            <span className="flex items-center gap-1">
              <Clock className="size-3.5" aria-hidden="true" />
              {event.duration_days} day{event.duration_days === 1 ? "" : "s"}
            </span>
          )}
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
