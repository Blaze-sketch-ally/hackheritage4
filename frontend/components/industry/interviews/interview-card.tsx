"use client";

import Link from "next/link";
import { Briefcase, CalendarClock, GraduationCap, MapPin, Video } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { InterviewStatusBadge } from "@/components/industry/interviews/interview-status-badge";
import { applicantRef, OPPORTUNITY_TYPE_LABELS } from "@/types/application";
import { INTERVIEW_MODE_LABELS, type Interview } from "@/types/interview";

export function formatInterviewWhen(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** One interview row for the interviews list. Candidate is shown only as
 * a privacy-safe reference (the schema exposes no student profile data). */
export function InterviewCard({
  interview,
  pending,
  onReschedule,
  onComplete,
  onCancel,
}: {
  interview: Interview;
  pending: boolean;
  onReschedule: () => void;
  onComplete: () => void;
  onCancel: () => void;
}) {
  const ref = applicantRef(interview.student_id);
  const opportunityTitle =
    interview.opportunity?.title ??
    (interview.opportunity_type
      ? OPPORTUNITY_TYPE_LABELS[interview.opportunity_type] ?? "Opportunity"
      : "Opportunity");
  const OppIcon = interview.opportunity_type === "INTERNSHIP" ? GraduationCap : Briefcase;
  const isOnline = interview.mode === "ONLINE";

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-0.5">
            <Link
              href={`/industry/interviews/${interview.id}`}
              className="block truncate font-medium hover:underline"
            >
              {ref}
            </Link>
            <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
              <OppIcon className="size-3.5 shrink-0" aria-hidden="true" />
              {opportunityTitle}
            </p>
          </div>
          <InterviewStatusBadge status={interview.status} />
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          <span className="inline-flex items-center gap-1">
            <CalendarClock className="size-3.5" aria-hidden="true" />
            {formatInterviewWhen(interview.scheduled_at)} · {interview.duration_minutes} min
          </span>
          <span className="inline-flex items-center gap-1">
            {isOnline ? (
              <Video className="size-3.5" aria-hidden="true" />
            ) : (
              <MapPin className="size-3.5" aria-hidden="true" />
            )}
            {INTERVIEW_MODE_LABELS[interview.mode]}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button size="sm" variant="outline" render={<Link href={`/industry/interviews/${interview.id}`} />}>
            View
          </Button>
          {interview.status === "SCHEDULED" ? (
            <>
              <Button size="sm" variant="outline" onClick={onReschedule} disabled={pending}>
                Reschedule
              </Button>
              <Button size="sm" onClick={onComplete} disabled={pending}>
                Mark complete
              </Button>
              <Button size="sm" variant="ghost" onClick={onCancel} disabled={pending}>
                Cancel
              </Button>
            </>
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
