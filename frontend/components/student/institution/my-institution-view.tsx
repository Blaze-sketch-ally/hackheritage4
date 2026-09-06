"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Briefcase,
  Building2,
  CalendarDays,
  CheckCircle2,
  FileText,
  Info,
  Landmark,
  MapPin,
  Sparkles,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { StatCard } from "@/components/dashboard/stat-card";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { ApiError } from "@/lib/api";
import { getMyInstitutionWorkspace } from "@/lib/student/institution";
import { InstitutionLinkCard } from "@/components/student/institution-link/institution-link-card";
import type {
  StudentActivityItem,
  StudentCuratedInternshipRow,
  StudentInstitutionEventRow,
  StudentInstitutionResponse,
  StudentPlacementDriveRow,
} from "@/types/student-institution";
import { EVENT_TYPE_LABELS } from "@/types/student-institution";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; data: StudentInstitutionResponse };

function formatDate(value: string | null): string {
  if (!value) return "—";
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function formatStipend(amount: number | null, currency: string | null): string {
  if (amount == null) return "Unpaid / not specified";
  return `${currency ?? ""} ${amount.toLocaleString()}`.trim();
}

/**
 * "My Institution" (Phase 12): a workspace built entirely from the
 * institution's own explicit curation/announcements -- never every
 * platform opportunity. Reuses institution_link_requests (via
 * InstitutionLinkCard) for the connect/pending states, and the existing
 * student opportunity apply flow for internships/jobs -- no duplicated
 * application logic here.
 */
export function MyInstitutionView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getMyInstitutionWorkspace()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your institution."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">My Institution</h1>
        <p className="text-sm text-muted-foreground">
          Placement drives, internships and events your institution has announced or curated for you.
        </p>
      </div>

      {state.status === "loading" ? <Loading label="Loading your institution…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={state.error.status === 401 ? "Your session has expired. Please sign in again." : state.error.message}
          onRetry={
            state.error.status !== 401
              ? () => {
                  setState({ status: "loading" });
                  setReloadKey((k) => k + 1);
                }
              : undefined
          }
        />
      ) : null}

      {state.status === "ready" && !state.data.linked ? <InstitutionLinkCard /> : null}

      {state.status === "ready" && state.data.linked ? <Ready data={state.data} /> : null}
    </div>
  );
}

function Ready({ data }: { data: StudentInstitutionResponse }) {
  const institution = data.institution;
  const profile = data.profile;

  return (
    <div className="space-y-6">
      <Card>
        <CardContent className="space-y-2">
          <div className="flex flex-wrap items-center gap-2">
            <Landmark className="size-5 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
            <h2 className="text-lg font-semibold">{institution?.institution_name ?? "Your institution"}</h2>
            <Badge variant="default" className="gap-1">
              <CheckCircle2 className="size-3.5" aria-hidden="true" /> Verified
            </Badge>
          </div>
          <div className="flex flex-wrap items-center gap-x-4 gap-y-1 text-sm text-muted-foreground">
            {profile?.department ? <span>{profile.department}</span> : null}
            {profile?.batch ? <span>Batch {profile.batch}</span> : null}
            {institution?.location ? (
              <span className="flex items-center gap-1">
                <MapPin className="size-3.5" aria-hidden="true" /> {institution.location}
              </span>
            ) : null}
          </div>
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Placement Drives" value={String(data.kpis.placement_drives)} icon={Briefcase} accent="indigo" />
        <StatCard label="Internships" value={String(data.kpis.internships)} icon={Sparkles} accent="violet" />
        <StatCard label="Upcoming Events" value={String(data.kpis.events)} icon={CalendarDays} accent="blue" />
        <StatCard label="Active Applications" value={String(data.kpis.active_applications)} icon={FileText} accent="emerald" />
      </div>

      <PlacementDrivesSection drives={data.placement_drives} />
      <InternshipsSection internships={data.internships} />
      <EventsSection events={data.events} />
      <ActivitySection activity={data.activity} />

      <div className="space-y-2">
        {[data.curation_note, data.eligibility_note, data.registration_note].map((note) => (
          <p
            key={note}
            className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground"
          >
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            {note}
          </p>
        ))}
      </div>
    </div>
  );
}

function PlacementDrivesSection({ drives }: { drives: StudentPlacementDriveRow[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Placement Drives</CardTitle>
      </CardHeader>
      <CardContent>
        {drives.length === 0 ? (
          <EmptyState icon={Briefcase} title="Your institution has not announced any placement drives yet." />
        ) : (
          <ul className="divide-y">
            {drives.map((d) => (
              <li key={d.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 space-y-1">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="font-medium">{d.title}</p>
                    <Badge variant="outline">{d.status}</Badge>
                    {d.is_eligible ? (
                      <Badge variant="default">Eligible</Badge>
                    ) : (
                      <Badge variant="secondary">Not eligible</Badge>
                    )}
                  </div>
                  <p className="text-xs text-muted-foreground">
                    {d.company_name ?? "Company"} · {d.mode ?? "Mode TBD"} · Deadline {formatDate(d.application_deadline)}
                  </p>
                  {!d.is_eligible && d.eligibility_reasons.length > 0 ? (
                    <p className="text-xs text-amber-600 dark:text-amber-400">{d.eligibility_reasons.join(", ")}</p>
                  ) : null}
                  {d.already_applied ? (
                    <p className="text-xs text-muted-foreground">You applied · {d.application_status}</p>
                  ) : null}
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  render={<Link href={`/student/jobs/job_${d.job_id}`} />}
                  nativeButton={false}
                >
                  View
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function InternshipsSection({ internships }: { internships: StudentCuratedInternshipRow[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Internships</CardTitle>
      </CardHeader>
      <CardContent>
        {internships.length === 0 ? (
          <EmptyState icon={Sparkles} title="No institution-curated internships are currently available." />
        ) : (
          <ul className="divide-y">
            {internships.map((i) => (
              <li key={i.id} className="flex flex-col gap-2 py-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0 space-y-1">
                  <p className="font-medium">{i.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {i.company_name ?? "Company"} · {i.work_mode ?? "Mode TBD"} ·{" "}
                    {formatStipend(i.stipend_amount, i.stipend_currency)}
                  </p>
                  {i.already_applied ? (
                    <p className="text-xs text-muted-foreground">You applied · {i.application_status}</p>
                  ) : null}
                </div>
                <Button
                  size="sm"
                  variant="outline"
                  render={<Link href={`/student/internships/internship_${i.id}`} />}
                  nativeButton={false}
                >
                  View
                </Button>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function EventsSection({ events }: { events: StudentInstitutionEventRow[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Events</CardTitle>
      </CardHeader>
      <CardContent>
        {events.length === 0 ? (
          <EmptyState icon={CalendarDays} title="No upcoming institution events." />
        ) : (
          <ul className="divide-y">
            {events.map((e) => (
              <li key={e.id} className="flex flex-col gap-1 py-3">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium">{e.title}</p>
                  <Badge variant="outline">{EVENT_TYPE_LABELS[e.event_type] ?? e.event_type}</Badge>
                  {e.is_relevant_to_me ? <Badge variant="default">For you</Badge> : null}
                </div>
                <p className="text-xs text-muted-foreground">
                  {formatDate(e.start_at)} {e.venue ? `· ${e.venue}` : ""} {e.company_name ? `· ${e.company_name}` : ""}
                </p>
                {e.description ? <p className="text-sm text-muted-foreground">{e.description}</p> : null}
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function ActivitySection({ activity }: { activity: StudentActivityItem[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Recent Activity</CardTitle>
      </CardHeader>
      <CardContent>
        {activity.length === 0 ? (
          <EmptyState icon={Building2} title="No activity yet." />
        ) : (
          <ul className="space-y-3">
            {activity.map((a, idx) => (
              <li key={`${a.type}-${a.occurred_at}-${idx}`} className="flex items-start justify-between gap-3 text-sm">
                <span>{a.label}</span>
                <span className="shrink-0 text-xs text-muted-foreground">{formatDate(a.occurred_at)}</span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
