"use client";

import { useCallback, useEffect, useState } from "react";
import { AlertCircle, Building2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { AcceptDeclinePanel } from "@/components/student/internship-workspace/accept-decline-panel";
import { ProgramPreview } from "@/components/student/internship-workspace/program-preview";
import { SkillPicker } from "@/components/student/internship-workspace/skill-picker";
import { WorkspaceAssignments } from "@/components/student/internship-workspace/workspace-assignments";
import { WorkspaceCompletion } from "@/components/student/internship-workspace/workspace-completion";
import { WorkspaceStatusBadge } from "@/components/student/internship-workspace/workspace-status-badge";
import { WorkspaceStipend } from "@/components/student/internship-workspace/workspace-stipend";
import { ApiError } from "@/lib/api";
import {
  acceptMyInternshipWorkspace,
  declineMyInternshipWorkspace,
  getMyInternshipWorkspace,
  setMyInternshipWorkspaceSkills,
} from "@/lib/student/internship-workspace";
import type { InternshipWorkspaceDetail } from "@/types/internship-workspace";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; workspace: InternshipWorkspaceDetail };

function title(ws: InternshipWorkspaceDetail): string {
  return ws.internship?.title?.trim() || ws.program?.title?.trim() || "Internship Workspace";
}

const STATE_MESSAGE: Partial<Record<string, string>> = {
  DECLINED: "You declined this internship offer.",
  RESCINDED: "This internship workspace is no longer active.",
};

export function InternshipWorkspaceView({ workspaceId }: { workspaceId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  const reload = useCallback(() => {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const workspace = await getMyInternshipWorkspace(workspaceId);
        if (!cancelled) setState({ status: "ready", workspace });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error:
            err instanceof ApiError
              ? err
              : new ApiError(0, "Could not load this internship workspace."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [workspaceId, reloadKey]);

  if (state.status === "loading") {
    return (
      <div className="space-y-4" aria-busy="true" aria-label="Loading internship workspace">
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
              {notFound
                ? "Internship workspace not found."
                : "Could not load this internship workspace."}
            </p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          {!notFound && (
            <Button variant="outline" size="sm" onClick={reload}>
              Try again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const ws = state.workspace;
  const status = ws.workspace_status;
  const acceptedLike = status === "ACCEPTED" || status === "IN_PROGRESS";
  // Once COMPLETED, skills/assignments stay READ-ONLY but must remain
  // visible -- certificate/workspace history is never hidden, even if the
  // internship posting itself later becomes CLOSED / ARCHIVED.
  const showHistory = acceptedLike || status === "COMPLETED";

  return (
    <div className="flex flex-col gap-6">
      <div className="flex flex-col gap-2">
        <div className="flex flex-wrap items-center gap-2">
          <h1 className="text-xl font-semibold">{title(ws)}</h1>
          <WorkspaceStatusBadge status={status} />
        </div>
        <div className="flex flex-wrap items-center gap-2 text-sm text-muted-foreground">
          <Badge variant="secondary">{ws.work_mode}</Badge>
          {ws.internship?.status ? (
            <span className="flex items-center gap-1">
              <Building2 className="size-3.5" aria-hidden="true" />
              Posting: {ws.internship.status}
            </span>
          ) : null}
        </div>
        {ws.internship?.description ? (
          <p className="max-w-prose text-sm text-muted-foreground">
            {ws.internship.description}
          </p>
        ) : null}
      </div>

      {status === "PENDING_ACCEPTANCE" && (
        <AcceptDeclinePanel
          onAccept={async () => {
            await acceptMyInternshipWorkspace(ws.id);
          }}
          onDecline={async (reason) => {
            await declineMyInternshipWorkspace(ws.id, reason);
          }}
          onAccepted={reload}
          onDeclined={reload}
        />
      )}

      {acceptedLike && (
        <Card>
          <CardContent className="py-4 text-sm">
            <span className="font-medium text-emerald-700 dark:text-emerald-400">
              Internship active.
            </span>{" "}
            Choose the training skills you want to focus on, then work through the
            program modules below.
          </CardContent>
        </Card>
      )}

      {(status === "DECLINED" || status === "RESCINDED") && (
        <Card>
          <CardContent className="py-6 text-center text-sm text-muted-foreground">
            {STATE_MESSAGE[status]}
          </CardContent>
        </Card>
      )}

      {acceptedLike && ws.program && (
        <SkillPicker
          skills={ws.program.skills}
          selectedSkillIds={ws.selected_skill_ids}
          onSave={async (skillIds) => {
            const updated = await setMyInternshipWorkspaceSkills(ws.id, skillIds);
            setState({ status: "ready", workspace: updated });
          }}
        />
      )}

      {showHistory && <WorkspaceCompletion workspaceId={ws.id} />}

      {showHistory && <WorkspaceStipend workspaceId={ws.id} />}

      {showHistory && <WorkspaceAssignments workspaceId={ws.id} />}

      {ws.program ? (
        <ProgramPreview program={ws.program} />
      ) : (
        <Card>
          <CardContent className="py-6 text-center text-sm text-muted-foreground">
            The industry hasn&apos;t published a training program for this internship
            yet.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
