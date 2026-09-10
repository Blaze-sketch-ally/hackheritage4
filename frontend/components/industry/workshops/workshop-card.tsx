"use client";

import Link from "next/link";
import { CalendarClock, MapPin, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { WorkshopActions } from "@/components/industry/workshops/workshop-actions";
import { WorkshopStatusBadge } from "@/components/industry/workshops/workshop-status-badge";
import { WORKSHOP_WORK_MODE_LABELS, type IndustryWorkshop } from "@/types/industry-workshop";

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

export function WorkshopCard({
  workshop,
  pending,
  onPublish,
  onClose,
  onArchive,
}: {
  workshop: IndustryWorkshop;
  pending: boolean;
  onPublish: () => void;
  onClose: () => void;
  onArchive: () => void;
}) {
  const detailHref = `/industry/workshops/${workshop.id}`;
  const canEdit = workshop.status === "DRAFT" || workshop.status === "PUBLISHED";
  const deadline = formatDate(workshop.application_deadline);

  const meta: Array<{ icon: typeof MapPin; text: string }> = [];
  if (workshop.location) meta.push({ icon: MapPin, text: workshop.location });
  if (workshop.work_mode) {
    meta.push({ icon: Users, text: WORKSHOP_WORK_MODE_LABELS[workshop.work_mode] });
  }
  if (workshop.duration_days) {
    meta.push({
      icon: CalendarClock,
      text: `${workshop.duration_days} day${workshop.duration_days === 1 ? "" : "s"}`,
    });
  }

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <Link href={detailHref} className="block truncate font-medium hover:underline">
              {workshop.title}
            </Link>
            <p className="text-xs text-muted-foreground">
              {workshop.capacity ? `${workshop.capacity} seat${workshop.capacity === 1 ? "" : "s"}` : "Capacity not set"}
              {deadline ? ` · Apply by ${deadline}` : ""}
            </p>
          </div>
          <WorkshopStatusBadge status={workshop.status} />
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
          <WorkshopActions
            status={workshop.status}
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
