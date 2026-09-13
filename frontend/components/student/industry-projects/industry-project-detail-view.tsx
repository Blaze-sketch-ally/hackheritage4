"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, ArrowUpRight, Building2, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { applyToProject, getProject, listMyProjectApplications } from "@/lib/student/industry-projects";
import { PROJECT_WORK_MODE_LABELS } from "@/types/industry-project";
import { PROJECT_APPLICATION_STATUS_LABELS, type ProjectApplication } from "@/types/project-application";
import type { StudentProject } from "@/types/student-project";

// Same eligibility set as the "My Applications" tab
// (industry-projects-list-view.tsx) -- kept local rather than shared,
// matching this codebase's existing per-area convention (each opportunity
// type owns its own copy of this tiny constant).
const WORKSPACE_ELIGIBLE = new Set(["SELECTED", "ACTIVE", "COMPLETED"]);

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; project: StudentProject; application: ProjectApplication | null };

function formatDate(value: string | null): string {
  if (!value) return "Not set";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  const empty = children == null || children === "";
  return (
    <div className="space-y-0.5">
      <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className={empty ? "text-sm text-muted-foreground/60" : "text-sm"}>{empty ? "Not set" : children}</dd>
    </div>
  );
}

export function IndustryProjectDetailView({ projectId }: { projectId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [applying, setApplying] = useState(false);
  const [confirmApply, setConfirmApply] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getProject(projectId),
      listMyProjectApplications()
        .then((r) => r.applications)
        .catch(() => [] as ProjectApplication[]),
    ])
      .then(([project, applications]) => {
        if (cancelled) return;
        const application = applications.find((a) => a.project_id === projectId) ?? null;
        setState({ status: "ready", project, application });
      })
      .catch((err) => {
        if (!cancelled)
          setState({
            status: "error",
            error: err instanceof ApiError ? err : new ApiError(0, "Could not load this project."),
          });
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, reloadKey]);

  async function handleApply() {
    setConfirmApply(false);
    setApplying(true);
    setActionError(null);
    try {
      const application = await applyToProject(projectId);
      setState((s) =>
        s.status === "ready" ? { ...s, project: { ...s.project, has_applied: true }, application } : s,
      );
      setActionSuccess("Application submitted.");
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Could not submit your application. Please try again.",
      );
    } finally {
      setApplying(false);
    }
  }

  return (
    <div className="space-y-6">
      <Link
        href="/student/industry-projects"
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> All projects
      </Link>

      {state.status === "loading" && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading…
          </CardContent>
        </Card>
      )}

      {state.status === "error" && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
            <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          </CardContent>
        </Card>
      )}

      {state.status === "ready" && (
        <>
          <FormError message={actionError} />
          <FormSuccess message={actionSuccess} />

          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
            <div className="min-w-0 space-y-1">
              <h1 className="text-xl font-semibold">{state.project.title}</h1>
              {state.project.industry.company_name && (
                <p className="flex items-center gap-1 text-sm text-muted-foreground">
                  <Building2 className="size-3.5" aria-hidden="true" />
                  {state.project.industry.company_name}
                </p>
              )}
            </div>
            {state.application ? (
              <div className="flex flex-col items-start gap-1.5 sm:items-end">
                <Badge variant="ghost">{PROJECT_APPLICATION_STATUS_LABELS[state.application.status]}</Badge>
                {WORKSPACE_ELIGIBLE.has(state.application.status) && (
                  <Button
                    size="sm"
                    render={<Link href={`/student/industry-projects/${projectId}/workspace`} />}
                    nativeButton={false}
                  >
                    Open Project Workspace <ArrowUpRight className="size-3.5" />
                  </Button>
                )}
              </div>
            ) : (
              <Button onClick={() => setConfirmApply(true)} disabled={applying}>
                Apply
              </Button>
            )}
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Details</CardTitle>
            </CardHeader>
            <CardContent>
              <dl className="grid gap-4 sm:grid-cols-2">
                <Detail label="Location">{state.project.location}</Detail>
                <Detail label="Work Mode">
                  {state.project.work_mode
                    ? PROJECT_WORK_MODE_LABELS[state.project.work_mode as keyof typeof PROJECT_WORK_MODE_LABELS]
                    : null}
                </Detail>
                <Detail label="Duration">
                  {state.project.duration_months != null ? `${state.project.duration_months} months` : null}
                </Detail>
                <Detail label="Team Size">{state.project.team_size ?? null}</Detail>
                <Detail label="Start Date">
                  {state.project.start_date ? formatDate(state.project.start_date) : null}
                </Detail>
                <Detail label="Application Deadline">
                  {state.project.application_deadline ? formatDate(state.project.application_deadline) : null}
                </Detail>
              </dl>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>Description</CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-sm whitespace-pre-line">{state.project.description}</p>
              {state.project.eligibility_criteria && (
                <>
                  <p className="mt-4 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                    Eligibility
                  </p>
                  <p className="text-sm whitespace-pre-line">{state.project.eligibility_criteria}</p>
                </>
              )}
            </CardContent>
          </Card>
        </>
      )}

      <ConfirmationDialog
        open={confirmApply}
        onOpenChange={setConfirmApply}
        title="Apply to this project?"
        confirmLabel="Apply"
        loading={applying}
        onConfirm={handleApply}
      />
    </div>
  );
}
