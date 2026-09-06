"use client";

import Link from "next/link";
import { Briefcase, CalendarClock, MapPin, Users, Wallet } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { JobActions } from "@/components/industry/jobs/job-actions";
import { JobStatusBadge } from "@/components/industry/jobs/job-status-badge";
import {
  EMPLOYMENT_TYPE_LABELS,
  WORK_MODE_LABELS,
  type EmploymentType,
  type Job,
  type WorkMode,
} from "@/types/job";

function formatSalary(min: number | null, max: number | null, currency: string | null): string | null {
  if (min == null && max == null) return null;
  const cur = currency ?? "INR";
  if (min != null && max != null) return `${cur} ${min.toLocaleString()}–${max.toLocaleString()}`;
  const one = (min ?? max) as number;
  return `${cur} ${one.toLocaleString()}${min != null ? "+" : " max"}`;
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

export function JobCard({
  job,
  pending,
  onPublish,
  onClose,
  onArchive,
}: {
  job: Job;
  pending: boolean;
  onPublish: () => void;
  onClose: () => void;
  onArchive: () => void;
}) {
  const detailHref = `/industry/jobs/${job.id}`;
  const canEdit = job.status === "DRAFT" || job.status === "PUBLISHED";
  const salary = formatSalary(job.salary_min, job.salary_max, job.salary_currency);
  const deadline = formatDate(job.application_deadline);

  const meta: Array<{ icon: typeof MapPin; text: string }> = [];
  if (job.employment_type) {
    meta.push({ icon: Briefcase, text: EMPLOYMENT_TYPE_LABELS[job.employment_type as EmploymentType] });
  }
  if (job.location) meta.push({ icon: MapPin, text: job.location });
  if (job.work_mode) meta.push({ icon: Users, text: WORK_MODE_LABELS[job.work_mode as WorkMode] });
  if (job.experience_min_years != null) {
    meta.push({ icon: CalendarClock, text: `${job.experience_min_years}+ yrs exp` });
  }
  if (salary) meta.push({ icon: Wallet, text: salary });

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <Link href={detailHref} className="block truncate font-medium hover:underline">
              {job.title}
            </Link>
            <p className="text-xs text-muted-foreground">
              {job.skills.length} required skill{job.skills.length === 1 ? "" : "s"}
              {job.openings ? ` · ${job.openings} opening${job.openings === 1 ? "" : "s"}` : ""}
              {deadline ? ` · Apply by ${deadline}` : ""}
            </p>
          </div>
          <JobStatusBadge status={job.status} />
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
          <JobActions
            status={job.status}
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
