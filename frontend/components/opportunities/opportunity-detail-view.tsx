"use client";

import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, MapPin } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { SkillMatchCard } from "@/components/opportunities/skill-match-card";
import { ApiError } from "@/lib/api";
import {
  applyToOpportunity,
  getOpportunity,
  getOpportunityMatch,
  listMyApplications,
} from "@/lib/student/opportunities";
import type { Application } from "@/types/application";
import type { Opportunity, OpportunityMatch } from "@/types/opportunity";

const TYPE_LABEL: Record<Opportunity["opportunity_type"], string> = {
  JOB: "Job",
  INTERNSHIP: "Internship",
};

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; opportunity: Opportunity; match: OpportunityMatch | null; existingApplication: Application | null };

/** The single opportunity detail implementation, rendered from three
 * routes (/student/opportunities/[id], /student/jobs/[id],
 * /student/internships/[id]) -- never a per-type duplicate. */
export function OpportunityDetailView({ opportunityId }: { opportunityId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [coverNote, setCoverNote] = useState("");
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  // The transition back to "loading" for a retry happens in the retry
  // button's onClick below, not here -- same
  // react-hooks/set-state-in-effect reasoning as OpportunityListView.
  // The initial mount already starts at "loading" via useState above.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [opportunity, { applications }] = await Promise.all([
          getOpportunity(opportunityId),
          listMyApplications(),
        ]);
        const existingApplication = applications.find((a) => a.opportunity_id === opportunityId) ?? null;

        let match: OpportunityMatch | null = null;
        try {
          match = await getOpportunityMatch(opportunityId);
        } catch {
          // Match is a nice-to-have on top of the opportunity itself --
          // if it fails (e.g. transient error), still show the posting.
          match = null;
        }

        if (cancelled) return;
        setState({ status: "ready", opportunity, match, existingApplication });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this opportunity."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [opportunityId, reloadKey]);

  async function handleApply() {
    setApplying(true);
    setApplyError(null);
    try {
      const application = await applyToOpportunity(opportunityId, coverNote.trim() || undefined);
      setState((prev) => (prev.status === "ready" ? { ...prev, existingApplication: application } : prev));
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(0, "Could not submit your application.");
      if (apiErr.status === 409) {
        setApplyError("You have already applied to this opportunity, or it's no longer accepting applications.");
      } else {
        setApplyError(apiErr.message);
      }
    } finally {
      setApplying(false);
    }
  }

  if (state.status === "loading") {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading opportunity">
        <Card className="animate-pulse">
          <CardContent className="space-y-2 py-6">
            <div className="h-5 w-1/2 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
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
              {state.error.status === 404 ? "This opportunity is not available." : "Could not load this opportunity."}
            </p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          {state.error.status !== 404 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setState({ status: "loading" });
                setReloadKey((k) => k + 1);
              }}
            >
              Try again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const { opportunity, match, existingApplication } = state;

  return (
    <div className="grid gap-6 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="secondary">{TYPE_LABEL[opportunity.opportunity_type]}</Badge>
              {opportunity.location && (
                <Badge variant="outline" className="gap-1">
                  <MapPin className="size-3" aria-hidden="true" />
                  {opportunity.location}
                </Badge>
              )}
            </div>
            <CardTitle className="text-xl">{opportunity.title}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {opportunity.description && <p className="text-sm text-muted-foreground">{opportunity.description}</p>}

            {existingApplication ? (
              <div className="flex items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2.5 text-sm">
                <CheckCircle2 className="size-4 text-emerald-600" aria-hidden="true" />
                <span className="font-medium">Applied</span>
                <span className="text-muted-foreground">
                  — your application is currently <strong>{existingApplication.status}</strong>.
                </span>
              </div>
            ) : (
              <div className="space-y-2">
                <Textarea
                  placeholder="Optional cover note — tell them why you're a good fit..."
                  value={coverNote}
                  onChange={(e) => setCoverNote(e.target.value)}
                  disabled={applying}
                  rows={3}
                />
                {applyError && <p className="text-sm text-destructive">{applyError}</p>}
                <Button onClick={handleApply} disabled={applying}>
                  {applying ? "Submitting..." : "Apply"}
                </Button>
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        {match && <SkillMatchCard overallScore={match.overall_score} skills={match.skills} />}
      </div>
    </div>
  );
}
