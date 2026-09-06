"use client";

import Link from "next/link";
import { Briefcase, CalendarDays, FileText, Gauge, GraduationCap } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApplicationStatusActions } from "@/components/industry/applicants/application-status-actions";
import { ApplicationStatusBadge } from "@/components/industry/applicants/application-status-badge";
import {
  OPPORTUNITY_TYPE_LABELS,
  applicantDisplayName,
  type Application,
  type IndustrySettableStatus,
} from "@/types/application";

/** Avatar initials from a display name — "Arunangshu Pal" -> "AP", a
 * single-word name -> its first two letters, an id-based
 * applicantRef fallback ("Applicant db8b0e39") -> its last two chars, same
 * as before this helper existed. */
function initials(displayName: string): string {
  const words = displayName.trim().split(/\s+/).filter(Boolean);
  if (words.length >= 2) {
    return (words[0][0] + words[words.length - 1][0]).toUpperCase();
  }
  return displayName.slice(-2).toUpperCase();
}

function formatDate(value: string | null): string | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Reusable candidate row for every recruitment view (Applicants mobile,
 * Shortlisted, Interviews, Selected). Shows only what the backend
 * returns — no fabricated student data. */
export function CandidateCard({
  application,
  pending,
  onPick,
  showActions = true,
}: {
  application: Application;
  pending: boolean;
  onPick: (target: IndustrySettableStatus) => void;
  showActions?: boolean;
}) {
  const detailHref = `/industry/applicants/${application.id}`;
  const applied = formatDate(application.applied_at);
  const opportunityTitle = application.opportunity?.title ?? "(posting unavailable)";
  const OppIcon = application.opportunity_type === "INTERNSHIP" ? GraduationCap : Briefcase;
  const name = applicantDisplayName(application);

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <Avatar size="sm" className="shrink-0">
              <AvatarFallback>{initials(name)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 space-y-0.5">
              <Link href={detailHref} className="block truncate font-medium hover:underline">
                {name}
              </Link>
              <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
                <OppIcon className="size-3.5 shrink-0" aria-hidden="true" />
                {OPPORTUNITY_TYPE_LABELS[application.opportunity_type]} · {opportunityTitle}
              </p>
            </div>
          </div>
          <ApplicationStatusBadge status={application.status} />
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {applied ? (
            <span className="inline-flex items-center gap-1">
              <CalendarDays className="size-3.5" aria-hidden="true" /> Applied {applied}
            </span>
          ) : null}
          {application.cover_note ? (
            <span className="inline-flex items-center gap-1">
              <FileText className="size-3.5" aria-hidden="true" /> Cover note
            </span>
          ) : null}
          <span className="inline-flex items-center gap-1">
            <Gauge className="size-3.5" aria-hidden="true" />
            {application.match_score != null
              ? `Match ${Math.round(application.match_score)}%`
              : "Not scored yet"}
          </span>
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button size="sm" variant="outline" render={<Link href={detailHref} />}>
            View
          </Button>
          {showActions ? (
            <ApplicationStatusActions
              status={application.status}
              pending={pending}
              onPick={onPick}
            />
          ) : null}
        </div>
      </CardContent>
    </Card>
  );
}
