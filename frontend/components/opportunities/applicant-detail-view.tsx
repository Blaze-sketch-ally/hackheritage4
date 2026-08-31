"use client";

import { useEffect, useState } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApplicationStatusBadge } from "@/components/opportunities/application-status-badge";
import { SkillMatchCard } from "@/components/opportunities/skill-match-card";
import { CertificationCard } from "@/components/portfolio/certification-card";
import { ProjectCard } from "@/components/portfolio/project-card";
import { ApiError } from "@/lib/api";
import { getApplicantDetail } from "@/lib/industry/opportunities";
import { getApplicationPortfolio } from "@/lib/industry/portfolio";
import type { ApplicantDetail } from "@/types/application";
import type { Portfolio } from "@/types/portfolio";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; applicant: ApplicantDetail; portfolio: Portfolio | null };

/** Phase 1N: the "Applicant" step of Industry -> My Opportunities ->
 * Applicants -> Applicant -> Portfolio. Candidate overview and skill
 * alignment reuse Phase 1M's SkillMatchCard/ApplicationStatusBadge
 * unchanged; portfolio reuses the exact ProjectCard/CertificationCard
 * the student's own portfolio pages use, rendered read-only (no
 * onEdit/onDelete passed) -- never a second display implementation.
 * Portfolio is fetched separately from the candidate overview/match and
 * treated as best-effort, matching OpportunityDetailView's own "a
 * secondary fetch failing must not block the primary content"
 * reasoning: an applicant with an empty or momentarily-unavailable
 * portfolio should still show their match score and status. */
export function ApplicantDetailView({
  opportunityId,
  applicationId,
}: {
  opportunityId: string;
  applicationId: string;
}) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [portfolioUnavailable, setPortfolioUnavailable] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const applicant = await getApplicantDetail(opportunityId, applicationId);

        let portfolio: Portfolio | null = null;
        try {
          portfolio = await getApplicationPortfolio(applicationId);
          if (!cancelled) setPortfolioUnavailable(false);
        } catch {
          if (!cancelled) setPortfolioUnavailable(true);
        }

        if (cancelled) return;
        setState({ status: "ready", applicant, portfolio });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this applicant."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [opportunityId, applicationId, reloadKey]);

  if (state.status === "loading") {
    return <div className="h-48 animate-pulse rounded-lg bg-muted" aria-busy="true" aria-label="Loading applicant" />;
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">
              {state.error.status === 404 ? "This applicant is not available." : "Could not load this applicant."}
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
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const { applicant, portfolio } = state;
  const hasPortfolio = portfolio && (portfolio.projects.length > 0 || portfolio.certifications.length > 0);

  return (
    <div className="grid gap-6 xl:grid-cols-3">
      <div className="space-y-6 xl:col-span-2">
        <Card>
          <CardHeader>
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle className="text-xl">{applicant.student_name ?? "Unknown"}</CardTitle>
              <ApplicationStatusBadge status={applicant.status} />
            </div>
          </CardHeader>
          <CardContent className="space-y-2">
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <span>Applied {new Date(applicant.created_at).toLocaleDateString()}</span>
              <Badge variant="secondary" className="tabular-nums">
                {Number(applicant.overall_match_score).toFixed(0)}% match
              </Badge>
            </div>
            {applicant.cover_note && (
              <p className="rounded-lg border bg-muted/30 p-3 text-sm">{applicant.cover_note}</p>
            )}
          </CardContent>
        </Card>

        <section className="space-y-3">
          <h2 className="text-lg font-semibold">Portfolio</h2>
          {portfolioUnavailable ? (
            <Card>
              <CardContent className="py-6 text-center text-sm text-muted-foreground">
                Portfolio is temporarily unavailable.
              </CardContent>
            </Card>
          ) : !hasPortfolio ? (
            <Card>
              <CardContent className="py-6 text-center text-sm text-muted-foreground">
                This candidate hasn&apos;t added any portfolio content yet.
              </CardContent>
            </Card>
          ) : (
            <div className="space-y-4">
              {portfolio!.projects.length > 0 && (
                <div className="grid gap-4 sm:grid-cols-2">
                  {portfolio!.projects.map((project) => (
                    <ProjectCard key={project.id} project={project} />
                  ))}
                </div>
              )}
              {portfolio!.certifications.length > 0 && (
                <div className="grid gap-4 sm:grid-cols-2">
                  {portfolio!.certifications.map((certification) => (
                    <CertificationCard key={certification.id} certification={certification} />
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      </div>

      <div className="space-y-4">
        <SkillMatchCard overallScore={applicant.overall_match_score} skills={applicant.skills} title="Skill Alignment" />
      </div>
    </div>
  );
}
