"use client";

import { useEffect, useState } from "react";
import { AlertCircle, RefreshCw } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { clearTargetJobRole, getSkillGap, listJobRoles, setTargetJobRole } from "@/lib/student/skill-gap";
import type { JobRole, SkillGapAnalysis } from "@/types/skill-gap";
import { TargetRoleSelector } from "@/components/student/skill-gap/target-role-selector";
import { JobRoleAnalysisView } from "@/components/student/skill-gap/job-role-analysis-view";
import { PersonalAnalysisView } from "@/components/student/skill-gap/personal-analysis-view";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; jobRoles: JobRole[]; analysis: SkillGapAnalysis };

/** GET /api/v1/job-roles + GET /api/v1/skill-gap -- the backend is the
 * only source of readiness/gap/priority/recommendation data; this
 * component only fetches, displays, and (for the target-role selector)
 * writes through the existing API. No gap calculation is duplicated here. */
export function SkillGapView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [saving, setSaving] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [{ job_roles }, analysis] = await Promise.all([listJobRoles(), getSkillGap()]);
        if (cancelled) return;
        setState({ status: "ready", jobRoles: job_roles, analysis });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your skill gap analysis."),
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  async function handleSelect(jobRoleId: string) {
    setSaving(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await setTargetJobRole(jobRoleId);
      const analysis = await getSkillGap();
      setState((prev) => (prev.status === "ready" ? { ...prev, analysis } : prev));
      setActionSuccess("Target role updated.");
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Could not set your target role. Please try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function handleClear() {
    setSaving(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      await clearTargetJobRole();
      const analysis = await getSkillGap();
      setState((prev) => (prev.status === "ready" ? { ...prev, analysis } : prev));
      setActionSuccess("Target role cleared.");
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Could not clear your target role. Please try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Skill Gap Analysis</h1>
        <p className="text-sm text-muted-foreground">
          Understand where you stand and what skills you should develop next.
        </p>
      </div>

      {state.status === "loading" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground" aria-busy="true">
            <p className="text-sm">Loading your skill gap analysis…</p>
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" />
            <div>
              <p className="font-medium">
                {state.error.status === 401
                  ? "Your session has expired. Please sign in again."
                  : "Could not load your skill gap analysis."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status !== 401 ? (
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
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? (
        <>
          <FormError message={actionError} />
          <FormSuccess message={actionSuccess} />

          <TargetRoleSelector
            jobRoles={state.jobRoles}
            selectedJobRoleId={state.analysis.mode === "JOB_ROLE" ? state.analysis.job_role.id : null}
            saving={saving}
            onSelect={handleSelect}
            onClear={handleClear}
          />

          {state.analysis.mode === "JOB_ROLE" ? (
            <JobRoleAnalysisView analysis={state.analysis} />
          ) : (
            <PersonalAnalysisView analysis={state.analysis} />
          )}
        </>
      ) : null}
    </div>
  );
}
