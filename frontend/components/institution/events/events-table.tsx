"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { CalendarDays, Search } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import type { EventRow } from "@/types/institution-event";
import { EVENT_STATUS_LABELS, EVENT_TYPE_LABELS } from "@/types/institution-event";

const ALL = "__all__";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  PUBLISHED: "default",
  ONGOING: "default",
  COMPLETED: "secondary",
  CANCELLED: "destructive",
  DRAFT: "outline",
};

function formatDateTime(value: string | null): string {
  if (!value) return "Date TBA";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "Date TBA";
  return parsed.toLocaleString(undefined, { month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit" });
}

const SECTIONS: { key: string; title: string; statuses: string[] }[] = [
  { key: "upcoming", title: "Upcoming", statuses: ["PUBLISHED"] },
  { key: "ongoing", title: "Ongoing", statuses: ["ONGOING"] },
  { key: "completed", title: "Completed", statuses: ["COMPLETED"] },
  { key: "other", title: "Draft / Cancelled", statuses: ["DRAFT", "CANCELLED"] },
];

/** The Institution Events directory (Phase 10, Part 4/5/21) -- grouped
 * into Upcoming/Ongoing/Completed sections by real status, with
 * search/type/status/mode filters. */
export function EventsTable({
  events,
  typeOptions,
  statusOptions,
  modeOptions,
}: {
  events: EventRow[];
  typeOptions: string[];
  statusOptions: string[];
  modeOptions: string[];
}) {
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState(ALL);
  const [statusFilter, setStatusFilter] = useState(ALL);
  const [modeFilter, setModeFilter] = useState(ALL);

  const filtered = useMemo(() => {
    let rows = events;
    if (typeFilter !== ALL) rows = rows.filter((r) => r.event_type === typeFilter);
    if (statusFilter !== ALL) rows = rows.filter((r) => r.status === statusFilter);
    if (modeFilter !== ALL) rows = rows.filter((r) => r.mode === modeFilter);
    const needle = search.trim().toLowerCase();
    if (needle) {
      rows = rows.filter((r) => r.title.toLowerCase().includes(needle) || (r.company_name ?? "").toLowerCase().includes(needle));
    }
    return rows;
  }, [events, search, typeFilter, statusFilter, modeFilter]);

  return (
    <div className="space-y-4">
      {events.length > 0 ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by title or company..."
              className="pl-8"
              aria-label="Search events"
            />
          </div>
          <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v ?? ALL)}>
            <SelectTrigger className="w-full sm:w-44" aria-label="Filter by event type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All types</SelectItem>
              {typeOptions.map((t) => (
                <SelectItem key={t} value={t}>
                  {EVENT_TYPE_LABELS[t] ?? t}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v ?? ALL)}>
            <SelectTrigger className="w-full sm:w-36" aria-label="Filter by status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {statusOptions.map((s) => (
                <SelectItem key={s} value={s}>
                  {EVENT_STATUS_LABELS[s] ?? s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={modeFilter} onValueChange={(v) => setModeFilter(v ?? ALL)}>
            <SelectTrigger className="w-full sm:w-36" aria-label="Filter by mode">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All modes</SelectItem>
              {modeOptions.map((m) => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {events.length === 0 ? (
        <EmptyState icon={CalendarDays} title="No events yet" description="Create your first event, or check back once companies publish workshops." />
      ) : filtered.length === 0 ? (
        <EmptyState icon={Search} title="No events match your filters" />
      ) : statusFilter !== ALL ? (
        <EventsSectionTable rows={filtered} />
      ) : (
        <div className="space-y-6">
          {SECTIONS.map((section) => {
            const rows = filtered.filter((r) => section.statuses.includes(r.status));
            if (rows.length === 0) return null;
            return (
              <div key={section.key} className="space-y-2">
                <h2 className="text-sm font-semibold text-muted-foreground">
                  {section.title} ({rows.length})
                </h2>
                <EventsSectionTable rows={rows} />
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}

function EventsSectionTable({ rows }: { rows: EventRow[] }) {
  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Event</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Date</TableHead>
              <TableHead>Mode / Venue</TableHead>
              <TableHead>Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((r) => (
              <TableRow key={`${r.source}-${r.id}`}>
                <TableCell className="font-medium">
                  <Link href={`/institution/events/${r.id}`} className="hover:underline">
                    {r.title}
                  </Link>
                </TableCell>
                <TableCell className="text-muted-foreground">{EVENT_TYPE_LABELS[r.event_type] ?? r.event_type}</TableCell>
                <TableCell className="text-muted-foreground">{r.company_name ?? "—"}</TableCell>
                <TableCell className="text-muted-foreground">{formatDateTime(r.start_at)}</TableCell>
                <TableCell className="text-muted-foreground">
                  {[r.mode, r.venue].filter(Boolean).join(" · ") || "—"}
                </TableCell>
                <TableCell>
                  <div className="flex flex-col gap-1">
                    <Badge variant={STATUS_VARIANT[r.status] ?? "outline"}>{EVENT_STATUS_LABELS[r.status] ?? r.status}</Badge>
                    {r.platform_wide ? <span className="text-[10px] text-muted-foreground">Industry-hosted</span> : null}
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
