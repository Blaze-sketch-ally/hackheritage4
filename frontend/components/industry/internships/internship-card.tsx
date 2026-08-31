"use client";

import Link from "next/link";
import { CalendarClock, MapPin, Users, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { InternshipActions } from "@/components/industry/internships/internship-actions";
import { InternshipStatusBadge } from "@/components/industry/internships/internship-status-badge";
import {
  WORK_MODE_LABELS,
  type Internship,
  type WorkMode,
} from "@/types/internship";

function formatStipend(amount: number | null, currency: string | null): string | null {
  if (amount == null) return null;
  return `${currency ?? "INR"} ${amount.toLocaleString()}/mo`;
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

export function InternshipCard({
  internship,
  pending,
  onPublish,
  onClose,
  onArchive,
}: {
  internship: Internship;
  pending: boolean;
  onPublish: () => void;
  onClose: () => void;
  onArchive: () => void;
}) {
  const detailHref = `/industry/internships/${internship.id}`;
  const canEdit = internship.status === "DRAFT" || internship.status === "PUBLISHED";
  const stipend = formatStipend(internship.stipend_amount, internship.stipend_currency);
  const deadline = formatDate(internship.application_deadline);

  const meta: Array<{ icon: typeof MapPin; text: string }> = [];
  if (internship.location) meta.push({ icon: MapPin, text: internship.location });
  if (internship.work_mode) {
    meta.push({ icon: Users, text: WORK_MODE_LABELS[internship.work_mode as WorkMode] });
  }
  if (internship.duration_months) {
    meta.push({ icon: CalendarClock, text: `${internship.duration_months} months` });
  }
  if (stipend) meta.push({ icon: Wallet, text: stipend });

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <Link href={detailHref} className="block truncate font-medium hover:underline">
              {internship.title}
            </Link>
            <p className="text-xs text-muted-foreground">
              {internship.skills.length} required skill{internship.skills.length === 1 ? "" : "s"}
              {deadline ? ` · Apply by ${deadline}` : ""}
            </p>
          </div>
          <InternshipStatusBadge status={internship.status} />
        </div>

        {meta.length > 0 ? (
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
            {meta.map(({ icon: Icon, text }) => (
              <span key={text} className="inline-flex items-center gap-1">
                <Icon className="size-3.5" aria-hidden="true" />
                {text}
              </span>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center gap-2 pt-1">
          <Button size="sm" variant="outline" render={<Link href={detailHref} />}>
            View
          </Button>
          {canEdit ? (
            <Button size="sm" variant="outline" render={<Link href={`${detailHref}?edit=1`} />}>
              Edit
            </Button>
          ) : null}
          <InternshipActions
            status={internship.status}
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
