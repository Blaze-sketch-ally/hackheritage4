"use client";

import { Briefcase, GraduationCap, Plus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import {
  applicantDisplayName,
  OPPORTUNITY_TYPE_LABELS,
  type Application,
} from "@/types/application";

/** A candidate whose application the recruitment pipeline has advanced to
 * INTERVIEW_SCHEDULED (applications.status, migration 020) but who has no
 * interview event booked yet -- e.g. moved to the stage straight from the
 * Applicants page. These belong in the Interviews panel (its whole point
 * is to show every interview-stage candidate); they are listed as
 * "awaiting scheduling" until an interview is booked. The only action is
 * to schedule -- it opens the same schedule dialog, preselected to this
 * candidate. */
export function AwaitingScheduleCard({
  application,
  onSchedule,
}: {
  application: Application;
  onSchedule: () => void;
}) {
  const OppIcon = application.opportunity_type === "INTERNSHIP" ? GraduationCap : Briefcase;
  const opportunityTitle =
    application.opportunity?.title ??
    OPPORTUNITY_TYPE_LABELS[application.opportunity_type] ??
    "Opportunity";

  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-3">
        <div className="min-w-0 space-y-0.5">
          <p className="truncate font-medium">{applicantDisplayName(application)}</p>
          <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
            <OppIcon className="size-3.5 shrink-0" aria-hidden="true" />
            {opportunityTitle}
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Badge variant="secondary">Interview not scheduled</Badge>
          <Button size="sm" onClick={onSchedule}>
            <Plus className="size-4" aria-hidden="true" /> Schedule
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}
