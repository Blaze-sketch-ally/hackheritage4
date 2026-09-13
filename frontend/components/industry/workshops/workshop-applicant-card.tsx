"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, CalendarDays, GraduationCap } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { WorkshopApplicationStatusActions } from "@/components/industry/workshops/workshop-application-status-actions";
import { WorkshopApplicationStatusBadge } from "@/components/industry/workshops/workshop-application-status-badge";
import { ensureWorkspace } from "@/lib/industry/participation";
import {
  workshopApplicantDisplayName,
  type IndustrySettableWorkshopStatus,
  type WorkshopApplication,
} from "@/types/workshop-application";

const WORKSPACE_ELIGIBLE = new Set(["ACCEPTED", "COMPLETED"]);

function initials(displayName: string): string {
  const words = displayName.trim().split(/\s+/).filter(Boolean);
  if (words.length >= 2) return (words[0][0] + words[words.length - 1][0]).toUpperCase();
  return displayName.slice(-2).toUpperCase();
}

function formatDate(value: string | null): string | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** One applicant row for a Workshop's Applicants view. Shows only
 * server-resolved, human-readable identity (name/institution/department/
 * graduation year/skills, via public.workshop_applicant_profiles) --
 * never a raw student_id as the primary label. */
export function WorkshopApplicantCard({
  application,
  pending,
  onPick,
}: {
  application: WorkshopApplication;
  pending: boolean;
  onPick: (target: IndustrySettableWorkshopStatus) => void;
}) {
  const name = workshopApplicantDisplayName(application);
  const applied = formatDate(application.applied_at);
  const router = useRouter();
  const [openingWorkspace, setOpeningWorkspace] = useState(false);

  async function openWorkspace() {
    setOpeningWorkspace(true);
    try {
      const ws = await ensureWorkspace({ kind: "WORKSHOP", workshop_application_id: application.id });
      router.push(`/industry/participation/workspaces/${ws.id}`);
    } finally {
      setOpeningWorkspace(false);
    }
  }

  return (
    <Card>
      <CardContent className="space-y-3">
        <div className="flex items-start justify-between gap-3">
          <div className="flex min-w-0 items-center gap-3">
            <Avatar size="sm" className="shrink-0">
              <AvatarFallback>{initials(name)}</AvatarFallback>
            </Avatar>
            <div className="min-w-0 space-y-0.5">
              <p className="truncate font-medium">{name}</p>
              <p className="flex flex-wrap items-center gap-x-3 gap-y-0.5 text-xs text-muted-foreground">
                {application.institution_name ? (
                  <span className="inline-flex items-center gap-1">
                    <Building2 className="size-3.5 shrink-0" aria-hidden="true" />
                    {application.institution_name}
                  </span>
                ) : null}
                {application.department || application.graduation_year ? (
                  <span className="inline-flex items-center gap-1">
                    <GraduationCap className="size-3.5 shrink-0" aria-hidden="true" />
                    {[application.department, application.graduation_year].filter(Boolean).join(" · ")}
                  </span>
                ) : null}
              </p>
            </div>
          </div>
          <WorkshopApplicationStatusBadge status={application.status} />
        </div>

        {application.skills && application.skills.length > 0 ? (
          <div className="flex flex-wrap gap-1.5">
            {application.skills.map((skill) => (
              <Badge key={skill} variant="secondary" className="text-xs">
                {skill}
              </Badge>
            ))}
          </div>
        ) : null}

        <div className="flex flex-wrap items-center justify-between gap-2 pt-1">
          {applied ? (
            <span className="inline-flex items-center gap-1 text-xs text-muted-foreground">
              <CalendarDays className="size-3.5" aria-hidden="true" /> Applied {applied}
            </span>
          ) : (
            <span />
          )}
          <div className="flex flex-wrap items-center gap-2">
            {WORKSPACE_ELIGIBLE.has(application.status) ? (
              <Button size="sm" variant="outline" onClick={openWorkspace} disabled={openingWorkspace}>
                Open Workspace
              </Button>
            ) : null}
            <WorkshopApplicationStatusActions status={application.status} pending={pending} onPick={onPick} />
          </div>
        </div>
      </CardContent>
    </Card>
  );
}
