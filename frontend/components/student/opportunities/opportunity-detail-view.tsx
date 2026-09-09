"use client";

import { useEffect, useState } from "react";
import {
  AlertCircle,
  Building2,
  CalendarDays,
  CheckCircle2,
  Clock,
  MapPin,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Textarea } from "@/components/ui/textarea";
import { SkillMatchCard } from "@/components/student/opportunities/skill-match-card";
import { ApplicationStatusBadge } from "@/components/student/opportunities/application-status-badge";
import { ApiError } from "@/lib/api";
import {
  applyToOpportunity,
  getOpportunity,
  getOpportunityMatch,
  listMyApplications,
} from "@/lib/student/opportunities";
import { EMPLOYMENT_TYPE_LABELS, type EmploymentType } from "@/types/job";
import type {
  OpportunityMatch,
  StudentApplication,
  StudentOpportunityDetail,
} from "@/types/student-opportunity";

const TYPE_LABEL = { JOB: "Job", INTERNSHIP: "Internship" } as const;

/** Currency-formatted amount (e.g. "₹15,000"), falling back to a plain
 * "<code> <number>" if the runtime doesn't recognise the currency code.
 * `currency` is whatever the API returned — never hardcoded. */
function money(amount: number, currency: string): string {
  try {
    return new Intl.NumberFormat(undefined, {
      style: "currency",
      currency,
      maximumFractionDigits: 0,
    }).format(amount);
  } catch {
    return `${currency} ${amount.toLocaleString()}`;
  }
}

/** A job's salary shown as a range, a floor, or a ceiling — whichever the
 * posting actually specifies. `null` when the posting lists no salary. */
function salaryRange(min: number | null, max: number | null, currency: string): string | null {
  if (min == null && max == null) return null;
  if (min != null && max != null) return `${money(min, currency)} – ${money(max, currency)}`;
  const one = (min ?? max) as number;
  return min != null ? `${money(one, currency)} and up` : `Up to ${money(one, currency)}`;
}

/** The compensation / logistics facts a student needs but that aren't
 * already shown as header badges (work mode, location) or in the meta row
 * (openings, duration, deadline). Only rows the posting actually fills in
 * are returned — no "Not set" placeholders. Every value comes straight
 * from `StudentOpportunityDetail`; nothing here is fabricated. */
function opportunityDetailRows(
  opportunity: StudentOpportunityDetail,
): Array<{ label: string; value: string }> {
  const rows: Array<{ label: string; value: string }> = [];

  if (opportunity.stipend_amount != null) {
    rows.push({
      label: "Stipend",
      value: `${money(opportunity.stipend_amount, opportunity.stipend_currency ?? "INR")} / month`,
    });
  }

  const salary = salaryRange(
    opportunity.salary_min,
    opportunity.salary_max,
    opportunity.salary_currency ?? "INR",
  );
  if (salary) rows.push({ label: "Salary", value: salary });

  if (opportunity.employment_type) {
    rows.push({
      label: "Employment type",
      value:
        EMPLOYMENT_TYPE_LABELS[opportunity.employment_type as EmploymentType] ??
        opportunity.employment_type,
    });
  }

  if (opportunity.experience_min_years != null) {
    rows.push({
      label: "Experience",
      value:
        opportunity.experience_min_years <= 0
          ? "No prior experience required"
          : `${opportunity.experience_min_years}+ year${
              opportunity.experience_min_years === 1 ? "" : "s"
            }`,
    });
  }

  if (opportunity.start_date) {
    const started = new Date(opportunity.start_date);
    if (!Number.isNaN(started.getTime())) {
      rows.push({ label: "Start date", value: started.toLocaleDateString() });
    }
  }

  return rows;
}

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | {
      status: "ready";
      opportunity: StudentOpportunityDetail;
      match: OpportunityMatch | null;
      existingApplication: StudentApplication | null;
    };

/** One implementation, rendered from /student/internships/[id] and
 * /student/jobs/[id]. `opportunityId` is the prefixed
 * `internship_<uuid>` / `job_<uuid>` string. */
export function OpportunityDetailView({ opportunityId }: { opportunityId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [coverNote, setCoverNote] = useState("");
  const [applying, setApplying] = useState(false);
  const [applyError, setApplyError] = useState<string | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [opportunity, { applications }] = await Promise.all([
          getOpportunity(opportunityId),
          listMyApplications(),
        ]);
        const existingApplication =
          applications.find((a) => a.opportunity?.id === opportunityId) ?? null;

        let match: OpportunityMatch | null = null;
        try {
          match = await getOpportunityMatch(opportunityId);
        } catch {
          // Match is advisory -- a failure here must never hide the
          // posting or block applying.
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
      setState((prev) =>
        prev.status === "ready" ? { ...prev, existingApplication: application } : prev,
      );
    } catch (err) {
      const apiErr = err instanceof ApiError ? err : new ApiError(0, "Could not submit your application.");
      setApplyError(
        apiErr.status === 409
          ? "You have already applied, or this posting is no longer accepting applications."
          : apiErr.message,
      );
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
            <div className="h-3 w-2/3 rounded bg-muted" />
          </CardContent>
        </Card>
      </div>
    );
  }

  if (state.status === "error") {
    const notFound = state.error.status === 404;
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">
              {notFound ? "This opportunity is not available." : "Could not load this opportunity."}
            </p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          {!notFound && (
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
  const company = opportunity.industry?.company_name;
  const detailRows = opportunityDetailRows(opportunity);

  return (
    <div className="grid gap-6 xl:grid-cols-3">
      <div className="space-y-4 xl:col-span-2">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center gap-1.5">
              <Badge variant="secondary">{TYPE_LABEL[opportunity.source_type]}</Badge>
              {opportunity.location && (
                <Badge variant="outline" className="gap-1">
                  <MapPin className="size-3" aria-hidden="true" />
                  {opportunity.location}
                </Badge>
              )}
              {opportunity.work_mode && <Badge variant="outline">{opportunity.work_mode}</Badge>}
            </div>
            <CardTitle className="text-xl">{opportunity.title}</CardTitle>
            {company && (
              <p className="flex items-center gap-1 text-sm text-muted-foreground">
                <Building2 className="size-3.5" aria-hidden="true" />
                {company}
                {opportunity.industry?.industry_sector
                  ? ` · ${opportunity.industry.industry_sector}`
                  : ""}
              </p>
            )}
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="flex flex-wrap gap-x-4 gap-y-1 text-sm text-muted-foreground">
              {opportunity.openings != null && (
                <span className="flex items-center gap-1">
                  <Users className="size-3.5" aria-hidden="true" />
                  {opportunity.openings} opening{opportunity.openings === 1 ? "" : "s"}
                </span>
              )}
              {opportunity.duration_months != null && (
                <span className="flex items-center gap-1">
                  <Clock className="size-3.5" aria-hidden="true" />
                  {opportunity.duration_months} months
                </span>
              )}
              {opportunity.application_deadline && (
                <span className="flex items-center gap-1">
                  <CalendarDays className="size-3.5" aria-hidden="true" />
                  Apply by {new Date(opportunity.application_deadline).toLocaleDateString()}
                </span>
              )}
            </div>

            {detailRows.length > 0 && (
              <div>
                <h3 className="text-sm font-medium">Details</h3>
                <dl className="mt-1.5 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                  {detailRows.flatMap((row) => [
                    <dt key={`${row.label}-label`} className="text-muted-foreground">
                      {row.label}
                    </dt>,
                    <dd key={`${row.label}-value`} className="font-medium">
                      {row.value}
                    </dd>,
                  ])}
                </dl>
              </div>
            )}

            <p className="text-sm whitespace-pre-wrap text-muted-foreground">
              {opportunity.description}
            </p>

            {opportunity.eligibility_criteria && (
              <div>
                <h3 className="text-sm font-medium">Eligibility</h3>
                <p className="text-sm whitespace-pre-wrap text-muted-foreground">
                  {opportunity.eligibility_criteria}
                </p>
              </div>
            )}

            {opportunity.skills.length > 0 && (
              <div>
                <h3 className="text-sm font-medium">Requirements</h3>
                <div className="mt-1.5 flex flex-wrap gap-1.5">
                  {opportunity.skills.map((skill) => (
                    <Badge key={skill.skill_id} variant="outline">
                      {skill.skill_name} · {skill.required_level}
                      {skill.importance === "CORE" ? " (core)" : ""}
                    </Badge>
                  ))}
                </div>
              </div>
            )}

            {existingApplication ? (
              <div className="flex flex-wrap items-center gap-2 rounded-lg border border-emerald-500/30 bg-emerald-500/5 px-3 py-2.5 text-sm">
                <CheckCircle2 className="size-4 text-emerald-600" aria-hidden="true" />
                <span className="font-medium">Applied</span>
                <span className="text-muted-foreground">— current status:</span>
                <ApplicationStatusBadge status={existingApplication.status} />
              </div>
            ) : (
              <div className="space-y-2">
                <label htmlFor="cover-note" className="text-sm font-medium">
                  Cover note <span className="text-muted-foreground">(optional)</span>
                </label>
                <Textarea
                  id="cover-note"
                  placeholder="Tell them why you're a good fit..."
                  value={coverNote}
                  onChange={(e) => setCoverNote(e.target.value)}
                  disabled={applying}
                  rows={3}
                  maxLength={5000}
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

      <div className="space-y-4">{match && <SkillMatchCard match={match} />}</div>
    </div>
  );
}
