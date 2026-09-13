"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { AlertCircle, Building2, CalendarDays, GraduationCap, Inbox, RefreshCw, Users } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { EmptyState } from "@/components/common/empty-state";
import { Filters } from "@/components/common/filters";
import { SearchBar } from "@/components/common/search-bar";
import { ApiError } from "@/lib/api";
import { listParticipants } from "@/lib/industry/participants";
import {
  PARTICIPANT_OPPORTUNITY_TYPE_LABELS,
  participantDisplayName,
  participantStatusLabel,
  type ParticipantOpportunityType,
  type ParticipantRecord,
} from "@/types/industry-participant";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; records: ParticipantRecord[] };

type View = "records" | "students";

const TYPE_FILTER_OPTIONS = [
  { value: "ALL", label: "All types" },
  ...Object.entries(PARTICIPANT_OPPORTUNITY_TYPE_LABELS).map(([value, label]) => ({ value, label })),
];

function formatDate(value: string | null): string | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function initials(displayName: string): string {
  const words = displayName.trim().split(/\s+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[words.length - 1][0]).toUpperCase();
  return displayName.slice(-2).toUpperCase();
}

function RecordRow({ record }: { record: ParticipantRecord }) {
  const applied = formatDate(record.applied_at);
  return (
    <Card>
      <CardContent className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
        <div className="min-w-0 space-y-0.5">
          <p className="font-medium">{participantDisplayName(record)}</p>
          <p className="flex flex-wrap items-center gap-1 text-xs text-muted-foreground">
            <Badge variant="secondary" className="text-[10px]">
              {PARTICIPANT_OPPORTUNITY_TYPE_LABELS[record.opportunity_type]}
            </Badge>
            <Link href={record.opportunity_href} className="hover:underline">
              {record.opportunity_title}
            </Link>
          </p>
        </div>
        <div className="flex items-center gap-3">
          {applied ? (
            <span className="hidden items-center gap-1 text-xs text-muted-foreground sm:inline-flex">
              <CalendarDays className="size-3.5" aria-hidden="true" /> {applied}
            </span>
          ) : null}
          <Badge variant="ghost">{participantStatusLabel(record)}</Badge>
        </div>
      </CardContent>
    </Card>
  );
}

function StudentGroup({ records }: { records: ParticipantRecord[] }) {
  const name = participantDisplayName(records[0]);
  const { institution_name, department, graduation_year } = records[0];
  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-center gap-3">
          <Avatar size="sm" className="shrink-0">
            <AvatarFallback>{initials(name)}</AvatarFallback>
          </Avatar>
          <div className="min-w-0">
            <p className="font-medium">{name}</p>
            <p className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
              {institution_name ? (
                <span className="inline-flex items-center gap-1">
                  <Building2 className="size-3.5 shrink-0" aria-hidden="true" />
                  {institution_name}
                </span>
              ) : null}
              {department || graduation_year ? (
                <span className="inline-flex items-center gap-1">
                  <GraduationCap className="size-3.5 shrink-0" aria-hidden="true" />
                  {[department, graduation_year].filter(Boolean).join(" · ")}
                </span>
              ) : null}
            </p>
          </div>
        </div>
        <div className="space-y-1.5 border-t pt-2">
          {records.map((r) => (
            <div key={r.id} className="flex items-center justify-between gap-2 text-sm">
              <p className="min-w-0 truncate">
                <Badge variant="secondary" className="mr-1.5 text-[10px]">
                  {PARTICIPANT_OPPORTUNITY_TYPE_LABELS[r.opportunity_type]}
                </Badge>
                <Link href={r.opportunity_href} className="hover:underline">
                  {r.opportunity_title}
                </Link>
              </p>
              <Badge variant="ghost" className="shrink-0">
                {participantStatusLabel(r)}
              </Badge>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}

/** Cross-module Industry Participant view -- composed server-side from
 * the four existing Applicants sources (Job/Internship, Project,
 * Workshop, Training). Two ways to read the same fetched list: a flat
 * "By Application" feed, and "By Student" grouping so an Industry account
 * can see everything one student has applied to across all of its own
 * postings in one place. */
export function ParticipantsView() {
  const [view, setView] = useState<View>("records");
  const [typeFilter, setTypeFilter] = useState("ALL");
  const [search, setSearch] = useState("");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    listParticipants({
      opportunityType: typeFilter === "ALL" ? undefined : (typeFilter as ParticipantOpportunityType),
      search,
    })
      .then(({ records }) => {
        if (!cancelled) setState({ status: "ready", records });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load participants."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [typeFilter, search, reloadKey]);

  const grouped = useMemo(() => {
    if (state.status !== "ready") return [];
    const byStudent = new Map<string, ParticipantRecord[]>();
    for (const record of state.records) {
      const list = byStudent.get(record.student_id) ?? [];
      list.push(record);
      byStudent.set(record.student_id, list);
    }
    return Array.from(byStudent.entries());
  }, [state]);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1.5">
          <Button variant={view === "records" ? "default" : "outline"} size="sm" onClick={() => setView("records")}>
            By Application
          </Button>
          <Button variant={view === "students" ? "default" : "outline"} size="sm" onClick={() => setView("students")}>
            By Student
          </Button>
        </div>
        <div className="flex flex-1 flex-wrap items-center justify-end gap-2 sm:flex-none">
          <SearchBar value={search} onChange={setSearch} placeholder="Search by student name…" />
          <Filters value={typeFilter} onChange={setTypeFilter} options={TYPE_FILTER_OPTIONS} aria-label="Opportunity type" />
        </div>
      </div>

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setState({ status: "loading" });
                setReloadKey((k) => k + 1);
              }}
            >
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" && state.records.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="No participants yet"
          description="Every applicant and participant across your Jobs, Internships, Projects, Workshops, and Training will show up here."
        />
      ) : null}

      {state.status === "ready" && state.records.length > 0 && view === "records" ? (
        <div className="space-y-2">
          {state.records.map((record) => (
            <RecordRow key={`${record.opportunity_type}-${record.id}`} record={record} />
          ))}
        </div>
      ) : null}

      {state.status === "ready" && state.records.length > 0 && view === "students" ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {grouped.map(([studentId, records]) => (
            <StudentGroup key={studentId} records={records} />
          ))}
        </div>
      ) : null}

      {state.status === "ready" && state.records.length > 0 ? (
        <p className="flex items-center gap-1 text-xs text-muted-foreground">
          <Users className="size-3.5" aria-hidden="true" />
          {state.records.length} record{state.records.length === 1 ? "" : "s"} · {grouped.length} student
          {grouped.length === 1 ? "" : "s"}
        </p>
      ) : null}
    </div>
  );
}
