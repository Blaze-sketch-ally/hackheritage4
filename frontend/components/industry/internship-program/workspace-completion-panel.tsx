"use client";

import { useEffect, useState } from "react";
import { Award, CheckCircle2, Circle, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { FormError } from "@/components/auth/form-error";
import { ApiError } from "@/lib/api";
import { getWorkspaceCompletion, verifyWorkspaceCompletion } from "@/lib/industry/internship-workspaces";
import type { CompletionSummary } from "@/types/internship-completion";

function fmt(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString();
}

/** One intern's completion status + the explicit verification action
 * (Phase 7). The backend is authoritative -- this only shows the
 * [Verify Internship Completion] button once requirements_met is true
 * and hides it once industry_verified, so a second certificate can never
 * be requested from here. */
export function WorkspaceCompletionPanel({
  workspaceId,
  studentName,
}: {
  workspaceId: string;
  studentName: string | null;
}) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "error"; message: string }
    | { status: "ready"; summary: CompletionSummary }
  >({ status: "loading" });
  const [confirmOpen, setConfirmOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getWorkspaceCompletion(workspaceId)
      .then((summary) => {
        if (!cancelled) setState({ status: "ready", summary });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load completion status.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  async function verify() {
    setBusy(true);
    setActionError(null);
    // Close the confirmation up front: on success the panel re-renders as
    // "completed"; on failure the dialog would otherwise stay open and
    // hide the error message + the retry button behind it.
    setConfirmOpen(false);
    try {
      const summary = await verifyWorkspaceCompletion(workspaceId);
      setState({ status: "ready", summary });
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Could not verify completion. Please try again.",
      );
    } finally {
      setBusy(false);
    }
  }

  if (state.status === "loading") {
    return <div className="h-16 animate-pulse rounded-lg bg-muted" aria-busy="true" />;
  }
  if (state.status === "error") {
    return <p className="text-sm text-destructive">{state.message}</p>;
  }

  const { summary } = state;

  return (
    <div className="flex flex-col gap-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="font-medium">{studentName ?? "Intern"}</p>
        <span className="text-sm text-muted-foreground">
          Requirements: {summary.completed_count} / {summary.required_count}
        </span>
      </div>

      {summary.outstanding.length > 0 && (
        <ul className="flex flex-col gap-1">
          {summary.outstanding.map((o) => (
            <li key={o.id} className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <Circle className="size-3 shrink-0" />
              {o.title}
            </li>
          ))}
        </ul>
      )}

      <FormError message={actionError} />

      {summary.industry_verified ? (
        <div className="flex items-center gap-2 text-sm">
          <CheckCircle2 className="size-4 text-emerald-600" />
          <span className="font-medium text-emerald-700 dark:text-emerald-400">
            Internship completed
          </span>
          {summary.certificate && (
            <span className="flex items-center gap-1 text-muted-foreground">
              <Award className="size-3.5" /> Certificate issued:{" "}
              <span className="font-mono">{summary.certificate.certificate_number}</span>
              <span>({fmt(summary.certificate.issued_at)})</span>
            </span>
          )}
        </div>
      ) : summary.requirements_met ? (
        <Button size="sm" className="w-fit" onClick={() => setConfirmOpen(true)} disabled={busy}>
          {busy && <Loader2 className="size-3.5 animate-spin" />}
          Verify Internship Completion
        </Button>
      ) : (
        <Badge variant="outline" className="w-fit">
          Verification not yet available
        </Badge>
      )}

      <ConfirmationDialog
        open={confirmOpen}
        onOpenChange={setConfirmOpen}
        title="Verify internship completion?"
        description={`This marks ${studentName ?? "this intern"}'s internship complete and issues a certificate. This cannot be undone.`}
        confirmLabel="Verify"
        loading={busy}
        onConfirm={() => {
          void verify();
        }}
      />
    </div>
  );
}
