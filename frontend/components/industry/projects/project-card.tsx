"use client";

import Link from "next/link";
import { CalendarClock, MapPin, Users } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ProjectActions } from "@/components/industry/projects/project-actions";
import { ProjectStatusBadge } from "@/components/industry/projects/project-status-badge";
import { PROJECT_WORK_MODE_LABELS, type IndustryProject } from "@/types/industry-project";

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

export function ProjectCard({
  project,
  pending,
  onPublish,
  onClose,
  onArchive,
}: {
  project: IndustryProject;
  pending: boolean;
  onPublish: () => void;
  onClose: () => void;
  onArchive: () => void;
}) {
  const detailHref = `/industry/projects/${project.id}`;
  const canEdit = project.status === "DRAFT" || project.status === "PUBLISHED";
  const deadline = formatDate(project.application_deadline);

  const meta: Array<{ icon: typeof MapPin; text: string }> = [];
  if (project.location) meta.push({ icon: MapPin, text: project.location });
  if (project.work_mode) {
    meta.push({ icon: Users, text: PROJECT_WORK_MODE_LABELS[project.work_mode] });
  }
  if (project.duration_months) {
    meta.push({
      icon: CalendarClock,
      text: `${project.duration_months} month${project.duration_months === 1 ? "" : "s"}`,
    });
  }

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="min-w-0 space-y-1">
            <Link href={detailHref} className="block truncate font-medium hover:underline">
              {project.title}
            </Link>
            <p className="text-xs text-muted-foreground">
              {project.team_size ? `${project.team_size} team member${project.team_size === 1 ? "" : "s"}` : "Team size not set"}
              {deadline ? ` · Apply by ${deadline}` : ""}
            </p>
          </div>
          <ProjectStatusBadge status={project.status} />
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
          <ProjectActions
            status={project.status}
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
