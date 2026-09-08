import Link from "next/link";
import { CalendarDays } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/common/empty-state";
import type { UpcomingEvent } from "@/types/institution-analytics";

function formatDate(value: string | null): string {
  if (!value) return "Date TBA";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Date TBA";
  return parsed.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

/** Phase 10: a compact preview merging the institution's own upcoming
 * organized events (`platform_wide: false`) with published Industry
 * workshops (`platform_wide: true`) -- see /institution/events for the
 * full workspace, linked below. Keeps the Dashboard concise; this is
 * not a second events UI. */
export function UpcomingEvents({ events }: { events: UpcomingEvent[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Upcoming Events</CardTitle>
        <p className="text-xs text-muted-foreground">
          Your organized events and published industry workshops.{" "}
          <Link href="/institution/events" className="text-indigo-600 hover:underline dark:text-indigo-400">
            View all events
          </Link>
          .
        </p>
      </CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <EmptyState icon={CalendarDays} title="No upcoming events" />
        ) : (
          <ul className="divide-y">
            {events.map((event) => (
              <li key={event.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{event.title}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {event.platform_wide ? "Industry workshop" : "Your event"}
                    {event.organizer ? ` · ${event.organizer}` : ""}
                  </p>
                </div>
                <span className="shrink-0 text-xs font-medium text-muted-foreground">
                  {formatDate(event.start_date)}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
