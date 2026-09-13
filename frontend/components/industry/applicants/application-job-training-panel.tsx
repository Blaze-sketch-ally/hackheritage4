"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, CheckCircle2, GraduationCap, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { ApiError } from "@/lib/api";
import { provisionJobTraining } from "@/lib/industry/applications";
import { getJobTrainingProgram } from "@/lib/industry/job-training";
import type { ApplicationProvisioning } from "@/types/application";

type ProgramState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "none" }
  | { status: "draft"; title: string }
  | { status: "published"; title: string };

type AssignState =
  | { status: "checking" }
  | { status: "not_assigned" }
  | { status: "assigned"; enrollmentId: string | null }
  | { status: "revoked" }
  | { status: "assigning" }
  | { status: "error"; message: string };

/** Read-only training-program status is checked on mount
 * (GET /jobs/{job_id}/training-program — never mutates).
 *
 * Whether the candidate is ALREADY assigned: right after this browser
 * session just ran the live SELECTED transition, `initialProvisioning`
 * already tells us definitively (set by application-detail-view.tsx from
 * that mutation's own response) and is trusted as-is, with no extra call.
 * On every OTHER mount (a fresh page load or a refresh, where
 * `initialProvisioning` is undefined), there is no dedicated read
 * endpoint for "does this application already have an enrollment" -- so
 * this panel resolves it by calling the existing, idempotent
 * provisionJobTraining() as a silent verify. That call is safe to run
 * this way because: it never touches applications.status; the backend
 * independently re-validates JOB + SELECTED + a published program before
 * ever creating a row (an ineligible application gets a harmless
 * SKIPPED_* no-op); an already-enrolled candidate gets back the exact
 * same ALREADY_EXISTS outcome the explicit "Assign Training" button
 * already treats as success; and creating the enrollment here (only when
 * genuinely eligible) merely completes the SELECTED transition's own
 * original best-effort provisioning attempt -- never something the
 * recruiter didn't already set in motion by selecting this candidate.
 * This replaces the previous behavior of defaulting to "not assigned"
 * whenever `initialProvisioning` was absent, which incorrectly showed
 * "Not assigned" + an "Assign Training" button for a real, already-active
 * enrollment on every refresh. */
export function ApplicationJobTrainingPanel({
  applicationId,
  jobId,
  initialProvisioning,
}: {
  applicationId: string;
  jobId: string;
  initialProvisioning?: ApplicationProvisioning | null;
}) {
  const [program, setProgram] = useState<ProgramState>({ status: "loading" });
  const [assign, setAssign] = useState<AssignState>(() => {
    if (initialProvisioning?.kind !== "JOB_TRAINING") return { status: "checking" };
    if (initialProvisioning.outcome === "REVOKED_BLOCKED") return { status: "revoked" };
    if (initialProvisioning.provisioned) {
      return { status: "assigned", enrollmentId: initialProvisioning.enrollment_id ?? null };
    }
    return { status: "not_assigned" };
  });
  const [confirming, setConfirming] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getJobTrainingProgram(jobId)
      .then((bundle) => {
        if (cancelled) return;
        if (!bundle.program) {
          setProgram({ status: "none" });
        } else if (bundle.program.status === "PUBLISHED") {
          setProgram({ status: "published", title: bundle.program.title });
        } else {
          setProgram({ status: "draft", title: bundle.program.title });
        }
      })
      .catch((err) => {
        if (cancelled) return;
        // A 404 means the caller doesn't own the job — indistinguishable
        // from "no program" for this read-only status check.
        if (err instanceof ApiError && err.status === 404) {
          setProgram({ status: "none" });
        } else {
          setProgram({ status: "error" });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [jobId]);

  // Resolves the "checking" state (see the component doc comment above) --
  // only once the program is confirmed published, matching the exact same
  // gating the explicit "Assign Training" button already uses: a draft
  // program can never have a real enrollment, so there is nothing to
  // silently verify against it.
  useEffect(() => {
    // "not_assigned" while draft/none/error/loading is never actually
    // rendered (see the `program.status === "published"` wrapper below),
    // so there is nothing to resolve until the program is confirmed
    // published -- this effect simply has no work to do until then, and
    // re-runs on its own once `program.status` changes.
    if (assign.status !== "checking" || program.status !== "published") return;
    let cancelled = false;
    provisionJobTraining(applicationId)
      .then((result) => {
        if (cancelled) return;
        if (result.outcome === "CREATED" || result.outcome === "ALREADY_EXISTS") {
          setAssign({ status: "assigned", enrollmentId: result.enrollment?.id ?? null });
        } else if (result.outcome === "REVOKED_BLOCKED") {
          setAssign({ status: "revoked" });
        } else {
          setAssign({ status: "not_assigned" });
        }
      })
      .catch(() => {
        if (cancelled) return;
        // Fail open to the same "not assigned" + button UX the panel
        // already had -- the button itself is a safe, idempotent retry.
        setAssign({ status: "not_assigned" });
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId, assign.status, program.status]);

  async function handleAssign() {
    setConfirming(false);
    setAssign({ status: "assigning" });
    try {
      const result = await provisionJobTraining(applicationId);
      if (result.outcome === "CREATED" || result.outcome === "ALREADY_EXISTS") {
        setAssign({ status: "assigned", enrollmentId: result.enrollment?.id ?? null });
      } else if (result.outcome === "REVOKED_BLOCKED") {
        setAssign({ status: "revoked" });
      } else {
        // SKIPPED_* — the application/job state changed underneath us
        // (e.g. no longer SELECTED). Surface it plainly and let the
        // recruiter retry after refreshing.
        setAssign({ status: "error", message: result.detail });
      }
    } catch (err) {
      setAssign({
        status: "error",
        message:
          err instanceof ApiError ? err.message : "Could not assign training. Please try again.",
      });
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GraduationCap className="size-4 text-muted-foreground" aria-hidden="true" />
          Training
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {program.status === "loading" ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-busy="true">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Checking training
            program…
          </p>
        ) : null}

        {program.status === "error" ? (
          <p className="text-sm text-muted-foreground">
            Could not check this job&apos;s training program right now.
          </p>
        ) : null}

        {program.status === "none" ? (
          <>
            <p className="text-sm text-muted-foreground">
              No training program published for this job yet.
            </p>
            <Button
              size="sm"
              variant="outline"
              render={<Link href={`/industry/jobs/${jobId}/training-program`} />}
              nativeButton={false}
            >
              Create Training Program
            </Button>
          </>
        ) : null}

        {program.status === "draft" ? (
          <>
            <p className="text-sm text-muted-foreground">
              Training program is not published yet.
            </p>
            <Button
              size="sm"
              variant="outline"
              render={<Link href={`/industry/jobs/${jobId}/training-program`} />}
              nativeButton={false}
            >
              Open Training Program
            </Button>
          </>
        ) : null}

        {program.status === "published" ? (
          <div className="space-y-3">
            <p className="text-sm font-medium">{program.title}</p>

            {assign.status === "checking" ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-busy="true">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Checking assignment
                status…
              </p>
            ) : assign.status === "assigned" ? (
              <p className="flex items-center gap-1.5 text-sm text-emerald-600">
                <CheckCircle2 className="size-4" aria-hidden="true" /> Training Assigned
              </p>
            ) : assign.status === "revoked" ? (
              <div className="flex items-start gap-1.5 text-sm text-muted-foreground">
                <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden="true" />
                <span>
                  This candidate&apos;s training enrollment was revoked. It is not re-assigned
                  automatically.
                </span>
              </div>
            ) : (
              <>
                <p className="text-sm text-muted-foreground">Status: Not assigned</p>
                {assign.status === "error" ? (
                  <p className="text-sm text-destructive">{assign.message}</p>
                ) : null}
                <Button
                  size="sm"
                  disabled={assign.status === "assigning"}
                  onClick={() => setConfirming(true)}
                >
                  {assign.status === "assigning" && <Loader2 className="size-3.5 animate-spin" />}
                  Assign Training
                </Button>
              </>
            )}
          </div>
        ) : null}
      </CardContent>

      <ConfirmationDialog
        open={confirming}
        onOpenChange={setConfirming}
        title="Assign training to this candidate?"
        description={
          program.status === "published"
            ? `This assigns this job's published training program, “${program.title}”, to this selected candidate.`
            : "This assigns this job's published training program to this selected candidate."
        }
        confirmLabel="Assign Training"
        loading={assign.status === "assigning"}
        onConfirm={handleAssign}
      />
    </Card>
  );
}
