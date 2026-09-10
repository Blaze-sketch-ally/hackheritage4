"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { CalendarDays } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getInstitutionEvents } from "@/lib/institution/events";
import type { EventRow } from "@/types/institution-event";
import { EVENT_STATUS_LABELS, EVENT_TYPE_LABELS } from "@/types/institution-event";

/**
 * Company Detail's "Events" section (Phase 10, Part 17/27) --
 * events (institution-organized or platform workshops) that feature
 * THIS company only, fetched via GET /institution/events?industry_id=...
 * -- the same directory the dedicated /institution/events page uses.
 * Links to the full event record; never duplicates event content.
 */
export function CompanyEventsCard({ industryId }: { industryId: string }) {
  const [events, setEvents] = useState<EventRow[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    getInstitutionEvents({ industry_id: industryId })
      .then(({ events: rows }) => {
        if (!cancelled) setEvents(rows);
      })
      .catch(() => {
        if (!cancelled) setEvents([]);
      });
    return () => {
      cancelled = true;
    };
  }, [industryId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Events</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {events == null ? (
          <p className="text-sm text-muted-foreground/70">Loading…</p>
        ) : events.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <CalendarDays className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">No events feature this company yet.</p>
          </div>
        ) : (
          <ul className="space-y-2">
            {events.map((e) => (
              <li key={`${e.source}-${e.id}`} className="flex items-center justify-between gap-2 text-sm">
                <Link href={`/institution/events/${e.id}`} className="min-w-0 truncate hover:underline">
                  {e.title}
                  <span className="ml-1 text-xs text-muted-foreground">{EVENT_TYPE_LABELS[e.event_type] ?? e.event_type}</span>
                </Link>
                <Badge variant="outline">{EVENT_STATUS_LABELS[e.status] ?? e.status}</Badge>
              </li>
            ))}
          </ul>
        )}
        <Link href="/institution/events" className="inline-block text-xs text-indigo-600 hover:underline dark:text-indigo-400">
          View All Events →
        </Link>
      </CardContent>
    </Card>
  );
}
