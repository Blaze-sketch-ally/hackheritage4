"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertTriangle, GraduationCap, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { provisionInternshipWorkspace } from "@/lib/industry/applications";
import { getInternshipProgram } from "@/lib/industry/internship-program";
import { WorkspaceStatusBadge } from "@/components/student/internship-workspace/workspace-status-badge";
import type { InternshipWorkspaceSummary, WorkspaceStatus } from "@/types/internship-workspace";

type ProgramState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "none" }
  | { status: "draft"; title: string }
  | { status: "published"; title: string };

type WorkspaceState =
  | { status: "checking" }
  | { status: "not_provisioned"; message: string }
  | { status: "provisioned"; workspace: InternshipWorkspaceSummary }
  | { status: "error"; message: string };

/** An honest note for the two terminal states that mean the workspace
 * exists but nothing further will happen — WorkspaceStatusBadge already
 * gives each a distinct color/label, this just explains it in a sentence. */
const TERMINAL_NOTE: Partial<Record<WorkspaceStatus, string>> = {
  DECLINED: "The student declined this internship offer.",
  RESCINDED: "This internship offer was withdrawn.",
};

/** Parallel to ApplicationJobTrainingPanel (same architecture), for the
 * INTERNSHIP side of a SELECTED application.
 *
 * Read-only internship-program status is checked on mount
 * (GET /internships/{internship_id}/program — never mutates).
 *
 * Whether a workspace already exists: unlike the Job Training panel, this
 * one has no "instant" shortcut from a live mutation response to trust,
 * because the SELECTED-transition's own inline provisioning summary
 * (ApplicationProvisioning) only ever carries an internship_id link
 * target for this kind, never the full workspace record (no
 * workspace_status, no workspace id) — there is nothing accurate to
 * render from it alone. So this panel always resolves its state the same
 * way, on every mount, by calling the existing, idempotent
 * provisionInternshipWorkspace() as a silent verify — never relying on
 * recentProvisioning / actionSuccess / createdWorkspaceId / any mutation
 * response. That call is safe to run this way for the same reasons the
 * Job Training panel's verify call is: it never touches
 * applications.status; the backend independently re-validates INTERNSHIP
 * + SELECTED + an eligible work_mode + an existing program before ever
 * creating a row (an ineligible application gets a harmless SKIPPED_*
 * no-op, shown here verbatim via the backend's own `detail` message);
 * ALREADY_EXISTS is treated identically to CREATED; and creating the
 * workspace here (only when genuinely eligible) merely completes the
 * SELECTED transition's own original best-effort provisioning attempt.
 * This is what makes "Open Workspace" survive a refresh, replacing the
 * previous one-shot link that only ever came from the live transition's
 * response and vanished the moment the page reloaded. */
export function ApplicationInternshipWorkspacePanel({
  applicationId,
  internshipId,
}: {
  applicationId: string;
  internshipId: string;
}) {
  const [program, setProgram] = useState<ProgramState>({ status: "loading" });
  const [workspace, setWorkspace] = useState<WorkspaceState>({ status: "checking" });

  useEffect(() => {
    let cancelled = false;
    getInternshipProgram(internshipId)
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
        // A 404 means the caller doesn't own the internship — indistinguishable
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
  }, [internshipId]);

  useEffect(() => {
    // A draft/missing program can never have a real workspace yet, and
    // "not_provisioned"/"checking" are never actually rendered outside the
    // `program.status === "published"` wrapper below -- so there is
    // nothing to resolve (and no write-shaped call worth making) until the
    // program is confirmed published. Matches the exact same gating the
    // Job Training panel uses for its own verify call.
    if (program.status !== "published") return;
    let cancelled = false;
    provisionInternshipWorkspace(applicationId)
      .then((result) => {
        if (cancelled) return;
        if ((result.outcome === "CREATED" || result.outcome === "ALREADY_EXISTS") && result.workspace) {
          setWorkspace({ status: "provisioned", workspace: result.workspace });
        } else {
          setWorkspace({ status: "not_provisioned", message: result.detail });
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setWorkspace({
          status: "error",
          message:
            err instanceof ApiError ? err.message : "Could not check the internship workspace.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [applicationId, program.status]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <GraduationCap className="size-4 text-muted-foreground" aria-hidden="true" />
          Internship Workspace
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {program.status === "loading" ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-busy="true">
            <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Checking internship
            program…
          </p>
        ) : null}

        {program.status === "error" ? (
          <p className="text-sm text-muted-foreground">
            Could not check this internship&apos;s program right now.
          </p>
        ) : null}

        {program.status === "none" ? (
          <>
            <p className="text-sm text-muted-foreground">
              No internship program created for this internship yet.
            </p>
            <Button
              size="sm"
              variant="outline"
              render={<Link href={`/industry/internships/${internshipId}/program`} />}
              nativeButton={false}
            >
              Create Internship Program
            </Button>
          </>
        ) : null}

        {program.status === "draft" ? (
          <>
            <p className="text-sm text-muted-foreground">
              Internship program is not published yet.
            </p>
            <Button
              size="sm"
              variant="outline"
              render={<Link href={`/industry/internships/${internshipId}/program`} />}
              nativeButton={false}
            >
              Open Internship Program
            </Button>
          </>
        ) : null}

        {program.status === "published" ? (
          <div className="space-y-3">
            <p className="text-sm font-medium">{program.title}</p>

            {workspace.status === "checking" ? (
              <p className="flex items-center gap-2 text-sm text-muted-foreground" aria-busy="true">
                <Loader2 className="size-4 animate-spin" aria-hidden="true" /> Checking workspace
                status…
              </p>
            ) : null}

            {workspace.status === "error" ? (
              <p className="text-sm text-destructive">{workspace.message}</p>
            ) : null}

            {workspace.status === "not_provisioned" ? (
              <p className="text-sm text-muted-foreground">{workspace.message}</p>
            ) : null}

            {workspace.status === "provisioned" ? (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <span className="text-sm text-muted-foreground">Workspace status:</span>
                  <WorkspaceStatusBadge status={workspace.workspace.workspace_status} />
                </div>
                {TERMINAL_NOTE[workspace.workspace.workspace_status] ? (
                  <div className="flex items-start gap-1.5 text-sm text-muted-foreground">
                    <AlertTriangle className="mt-0.5 size-4 shrink-0 text-amber-600" aria-hidden="true" />
                    <span>{TERMINAL_NOTE[workspace.workspace.workspace_status]}</span>
                  </div>
                ) : null}
                <Button
                  size="sm"
                  render={<Link href={`/industry/internships/${internshipId}/submissions`} />}
                  nativeButton={false}
                >
                  Open Workspace
                </Button>
              </div>
            ) : null}
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
