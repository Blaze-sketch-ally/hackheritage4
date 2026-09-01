"use client";

import Link from "next/link";
import { CalendarClock, MapPin, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { MentorshipActions } from "@/components/industry/mentorship/mentorship-actions";
import { MentorshipStatusBadge } from "@/components/industry/mentorship/mentorship-status-badge";
import { MENTORSHIP_WORK_MODE_LABELS, type IndustryMentorship } from "@/types/industry-mentorship";

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

export function MentorshipCard({
  mentorship,
  pending,
  onPublish,
  onClose,
  onArchive,
}: {
  mentorship: IndustryMentorship;
  pending: boolean;
  onPublish: () => void;
  onClose: () => void;
  onArchive: () => void;
}) {
  const detailHref = `/industry/mentorship/${mentorship.id}`;
  const canEdit = mentorship.status === "DRAFT" || mentorship.status === "PUBLISHED";
  const deadline = formatDate(mentorship.application_deadline);

  const meta: Array<{ icon: typeof MapPin; text: string }> = [
    { icon: MapPin, text: mentorship.location },
    { icon: Users, text: MENTORSHIP_WORK_MODE_LABELS[mentorship.work_mode] },
    {
      icon: CalendarClock,
      text: `${mentorship.duration_months} month${mentorship.duration_months === 1 ? "" : "s"}`,
    },
  ];

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <Link href={detailHref} className="block truncate font-medium hover:underline">
              {mentorship.title}
            </Link>
            <p className="text-xs text-muted-foreground">
              {mentorship.capacity} mentee{mentorship.capacity === 1 ? "" : "s"}
              {deadline ? ` · Apply by ${deadline}` : ""}
            </p>
          </div>
          <MentorshipStatusBadge status={mentorship.status} />
        </div>

        <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
          {meta.map(({ icon: Icon, text }) => (
            <span key={text} className="inline-flex items-center gap-1">
              <Icon className="size-3.5" aria-hidden="true" />
              {text}
            </span>
          ))}
        </div>

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button size="sm" variant="outline" render={<Link href={detailHref} />}>
            View
          </Button>
          {canEdit ? (
            <Button size="sm" variant="outline" render={<Link href={`${detailHref}?edit=1`} />}>
              Edit
            </Button>
          ) : null}
          <MentorshipActions
            status={mentorship.status}
            pending={pending}
            onPublish={onPublish}
            onClose={onClose}
            onArchive={onArchive}
          />
        </div>
      </CardContent>
    </Card>
  );
}
