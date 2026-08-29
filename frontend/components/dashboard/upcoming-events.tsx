import Link from "next/link";
import { CalendarDays } from "lucide-react";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import type { DashboardEvent } from "@/lib/mock/student-dashboard";

const TYPE_LABEL: Record<DashboardEvent["type"], string> = {
  assessment: "Assessment",
  workshop: "Workshop",
  drive: "Internship Drive",
  announcement: "Announcement",
};

export function UpcomingEvents({ events, viewAllHref }: { events: DashboardEvent[]; viewAllHref: string }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>Upcoming & Announcements</CardTitle>
        <CardAction>
          <Button variant="ghost" size="sm" render={<Link href={viewAllHref} />} nativeButton={false}>
            View All
          </Button>
        </CardAction>
      </CardHeader>
      <CardContent className="space-y-3">
        {events.map((event) => (
          <div key={event.id} className="flex items-start gap-3 rounded-lg border border-border/60 p-3">
            <span className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
              <CalendarDays className="size-4" aria-hidden="true" />
            </span>
            <div className="min-w-0 flex-1 space-y-0.5">
              <p className="truncate text-sm font-medium">{event.title}</p>
              <p className="text-xs text-muted-foreground">{event.date}</p>
            </div>
            <Badge variant="outline" className="shrink-0">
              {TYPE_LABEL[event.type]}
            </Badge>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}
