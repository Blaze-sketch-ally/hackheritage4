"use client";

import Link from "next/link";
import { CalendarClock, MapPin, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { TrainingActions } from "@/components/industry/training/training-actions";
import { TrainingStatusBadge } from "@/components/industry/training/training-status-badge";
import { TRAINING_WORK_MODE_LABELS, type IndustryTraining } from "@/types/industry-training";

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

export function TrainingCard({
  training,
  pending,
  onPublish,
  onClose,
  onArchive,
}: {
  training: IndustryTraining;
  pending: boolean;
  onPublish: () => void;
  onClose: () => void;
  onArchive: () => void;
}) {
  const detailHref = `/industry/training/${training.id}`;
  const canEdit = training.status === "DRAFT" || training.status === "PUBLISHED";
  const deadline = formatDate(training.application_deadline);

  const meta: Array<{ icon: typeof MapPin; text: string }> = [];
  if (training.location) meta.push({ icon: MapPin, text: training.location });
  if (training.work_mode) {
    meta.push({ icon: Users, text: TRAINING_WORK_MODE_LABELS[training.work_mode] });
  }
  if (training.duration_months) {
    meta.push({
      icon: CalendarClock,
      text: `${training.duration_months} month${training.duration_months === 1 ? "" : "s"}`,
    });
  }

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <Link href={detailHref} className="block truncate font-medium hover:underline">
              {training.title}
            </Link>
            <p className="text-xs text-muted-foreground">
              {training.capacity ? `${training.capacity} seat${training.capacity === 1 ? "" : "s"}` : "Capacity not set"}
              {deadline ? ` · Apply by ${deadline}` : ""}
            </p>
          </div>
          <TrainingStatusBadge status={training.status} />
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
          <TrainingActions
            status={training.status}
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
