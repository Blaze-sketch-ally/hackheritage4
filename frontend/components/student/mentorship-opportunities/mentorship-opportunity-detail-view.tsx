"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Building2, CalendarDays, Clock, Info, MapPin, RefreshCw, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { getMentorshipOpportunity } from "@/lib/student/mentorship-opportunities";
import { STUDENT_MENTORSHIP_OPPORTUNITY_WORK_MODE_LABELS } from "@/types/student-mentorship-opportunity";
import type { StudentMentorshipOpportunityDetail } from "@/types/student-mentorship-opportunity";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string; notFound: boolean }
  | { status: "ready"; mentorship: StudentMentorshipOpportunityDetail };

export function MentorshipOpportunityDetailView({ mentorshipId }: { mentorshipId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getMentorshipOpportunity(mentorshipId)
      .then((mentorship) => {
        if (!cancelled) setState({ status: "ready", mentorship });
      })
      .catch((err) => {
        if (cancelled) return;
        const apiErr = err instanceof ApiError ? err : null;
        setState({
          status: "error",
          message: apiErr?.message ?? "Could not load this mentorship opportunity.",
          notFound: apiErr?.status === 404,
        });
      });
    return () => {
      cancelled = true;
    };
  }, [mentorshipId, reloadKey]);

  if (state.status === "loading") {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading mentorship opportunity">
        <Card className="animate-pulse">
          <CardContent className="space-y-2 py-6">
            <div className="h-5 w-1/2 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-2/3 rounded bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">
              {state.notFound ? "This mentorship opportunity is not available." : "Could not load this mentorship opportunity."}
            </p>
            {!state.notFound && <p className="text-sm text-muted-foreground">{state.message}</p>}
          </div>
          {!state.notFound && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setState({ status: "loading" });
                setReloadKey((k) => k + 1);
              }}
            >
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const { mentorship } = state;
  const organizer = mentorship.organizer?.company_name;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-1.5">
            <Badge variant="secondary">
              {STUDENT_MENTORSHIP_OPPORTUNITY_WORK_MODE_LABELS[mentorship.work_mode]}
            </Badge>
            {mentorship.location && (
              <Badge variant="outline" className="gap-1">
                <MapPin className="size-3" aria-hidden="true" />
                {mentorship.location}
              </Badge>
            )}
          </div>
          <CardTitle className="text-xl">{mentorship.title}</CardTitle>
          {organizer && (
            <p className="flex items-center gap-1 text-sm text-muted-foreground">
              <Building2 className="size-3.5" aria-hidden="true" />
              {organizer}
              {mentorship.organizer?.industry_sector
                ? ` · ${mentorship.organizer.industry_sector}`
                : ""}
            </p>
          )}
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
            <span className="flex items-center gap-1">
              <Clock className="size-3.5" aria-hidden="true" />
              {mentorship.duration_months} month{mentorship.duration_months === 1 ? "" : "s"}
            </span>
            <span className="flex items-center gap-1">
              <Users className="size-3.5" aria-hidden="true" />
              {mentorship.capacity} place{mentorship.capacity === 1 ? "" : "s"}
            </span>
            {mentorship.start_date && (
              <span className="flex items-center gap-1">
                <CalendarDays className="size-3.5" aria-hidden="true" />
                Starts {new Date(mentorship.start_date).toLocaleDateString()}
              </span>
            )}
            {mentorship.application_deadline && (
              <span className="flex items-center gap-1">
                <CalendarDays className="size-3.5" aria-hidden="true" />
                Apply by {new Date(mentorship.application_deadline).toLocaleDateString()}
              </span>
            )}
          </div>

          <p className="text-sm whitespace-pre-wrap text-muted-foreground">
            {mentorship.description}
          </p>

          {mentorship.eligibility_criteria && (
            <div>
              <h3 className="text-sm font-medium">Eligibility</h3>
              <p className="text-sm whitespace-pre-wrap text-muted-foreground">
                {mentorship.eligibility_criteria}
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {!mentorship.requests_available && (
        <div className="flex items-start gap-2 rounded-lg border border-border/60 bg-muted/40 px-3 py-2.5 text-sm text-muted-foreground">
          <Info className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>
            Sending a mentorship request from the portal isn&apos;t available yet. Use the
            application deadline and eligibility details above, and contact the organiser directly
            if you&apos;d like to take part.
          </span>
        </div>
      )}
    </div>
  );
}
