"use client";

import { useEffect, useState } from "react";
import { Landmark, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { FormError } from "@/components/auth/form-error";
import { StipendStatusBadge } from "@/components/common/stipend-status-badge";
import { ApiError } from "@/lib/api";
import {
  approveWorkspaceStipend,
  cancelWorkspaceStipend,
  createWorkspaceStipend,
  getWorkspaceStipend,
  releaseWorkspaceStipend,
  updateWorkspaceStipend,
} from "@/lib/industry/internship-workspaces";
import type { CreateStipendInput, Stipend } from "@/types/internship-stipend";

function fmt(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString();
}

function StipendForm({
  stipend,
  busy,
  onSubmit,
  onCancel,
}: {
  stipend?: Stipend;
  busy: boolean;
  onSubmit: (data: CreateStipendInput) => void;
  onCancel?: () => void;
}) {
  const [amount, setAmount] = useState(stipend ? String(stipend.amount) : "");
  const [currency, setCurrency] = useState(stipend?.currency ?? "INR");
  const [reference, setReference] = useState(stipend?.reference ?? "");
  const [notes, setNotes] = useState(stipend?.notes ?? "");

  const parsed = Number(amount);
  const invalid = amount.trim() === "" || Number.isNaN(parsed) || parsed < 0;

  return (
    <div className="flex flex-col gap-2 rounded-lg border border-dashed p-3">
      <div className="grid gap-2 sm:grid-cols-[1fr_6rem]">
        <div className="space-y-1.5">
          <Label htmlFor="stipend-amount">Amount</Label>
          <Input
            id="stipend-amount"
            type="number"
            min={0}
            step="0.01"
            value={amount}
            onChange={(e) => setAmount(e.target.value)}
            disabled={busy}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="stipend-currency">Currency</Label>
          <Input
            id="stipend-currency"
            value={currency}
            onChange={(e) => setCurrency(e.target.value.toUpperCase())}
            maxLength={10}
            disabled={busy}
          />
        </div>
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="stipend-reference">Reference (optional)</Label>
        <Input
          id="stipend-reference"
          value={reference}
          onChange={(e) => setReference(e.target.value)}
          placeholder="e.g. internal payroll reference"
          disabled={busy}
        />
      </div>
      <div className="space-y-1.5">
        <Label htmlFor="stipend-notes">Notes (optional)</Label>
        <Textarea
          id="stipend-notes"
          value={notes}
          onChange={(e) => setNotes(e.target.value)}
          rows={2}
          disabled={busy}
        />
      </div>
      <div className="flex gap-2">
        <Button
          size="sm"
          disabled={busy || invalid}
          onClick={() =>
            onSubmit({
              amount: parsed,
              currency: currency.trim() || "INR",
              reference: reference.trim() || null,
              notes: notes.trim() || null,
            })
          }
        >
          {busy && <Loader2 className="size-3.5 animate-spin" />}
          {stipend ? "Save changes" : "Configure stipend"}
        </Button>
        {onCancel && (
          <Button size="sm" variant="ghost" onClick={onCancel} disabled={busy}>
            Cancel
          </Button>
        )}
      </div>
    </div>
  );
}

type PendingAction = "release" | "cancel" | null;

/** Industry stipend management for one workspace (Phase 8).
 * RECORD-KEEPING ONLY -- there is no payment gateway anywhere in this
 * component; [Release] only records that a disbursement happened. The
 * backend state machine is authoritative -- only the actions valid for
 * the current status are shown. */
export function WorkspaceStipendPanel({
  workspaceId,
  studentName,
}: {
  workspaceId: string;
  studentName: string | null;
}) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "error"; message: string }
    | { status: "ready"; stipend: Stipend | null }
  >({ status: "loading" });
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [pendingAction, setPendingAction] = useState<PendingAction>(null);

  useEffect(() => {
    let cancelled = false;
    getWorkspaceStipend(workspaceId)
      .then((summary) => {
        if (!cancelled) setState({ status: "ready", stipend: summary.stipend });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load stipend status.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  async function run(fn: () => Promise<{ stipend: Stipend | null }>) {
    setBusy(true);
    setActionError(null);
    try {
      const summary = await fn();
      setState({ status: "ready", stipend: summary.stipend });
      setEditing(false);
      setPendingAction(null);
    } catch (err) {
      setActionError(
        err instanceof Error ? err.message : "Could not complete that action. Please try again.",
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

  const { stipend } = state;

  return (
    <div className="flex flex-col gap-2 rounded-lg border p-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="flex items-center gap-1.5 font-medium">
          <Landmark className="size-4 text-muted-foreground" />
          {studentName ?? "Intern"}
        </p>
        {stipend && <StipendStatusBadge status={stipend.disbursement_status} />}
      </div>

      <FormError message={actionError} />

      {stipend === null ? (
        editing ? (
          <StipendForm
            busy={busy}
            onCancel={() => setEditing(false)}
            onSubmit={(data) => void run(() => createWorkspaceStipend(workspaceId, data))}
          />
        ) : (
          <Button size="sm" variant="outline" className="w-fit" onClick={() => setEditing(true)}>
            Configure stipend
          </Button>
        )
      ) : editing && stipend.disbursement_status === "PENDING" ? (
        <StipendForm
          stipend={stipend}
          busy={busy}
          onCancel={() => setEditing(false)}
          onSubmit={(data) => void run(() => updateWorkspaceStipend(workspaceId, data))}
        />
      ) : (
        <>
          <p className="text-sm">
            {stipend.amount} {stipend.currency}
            {stipend.disbursement_status === "RELEASED" && (
              <span className="text-muted-foreground"> · released {fmt(stipend.released_at)}</span>
            )}
          </p>
          <div className="flex flex-wrap gap-2">
            {stipend.disbursement_status === "PENDING" && (
              <>
                <Button size="sm" variant="outline" onClick={() => setEditing(true)} disabled={busy}>
                  Edit
                </Button>
                <Button
                  size="sm"
                  disabled={busy}
                  onClick={() => void run(() => approveWorkspaceStipend(workspaceId))}
                >
                  {busy && <Loader2 className="size-3.5 animate-spin" />}
                  Approve
                </Button>
                <Button
                  size="sm"
                  variant="outline"
                  disabled={busy}
                  onClick={() => setPendingAction("cancel")}
                >
                  Cancel stipend
                </Button>
              </>
            )}
            {stipend.disbursement_status === "APPROVED" && (
              <Button size="sm" disabled={busy} onClick={() => setPendingAction("release")}>
                Release stipend
              </Button>
            )}
          </div>
        </>
      )}

      <ConfirmationDialog
        open={pendingAction === "release"}
        onOpenChange={(open) => !open && setPendingAction(null)}
        title="Release this stipend?"
        description="This records the stipend as released in the portal. It does not process a payment -- disburse the funds through your usual channel first. This cannot be undone."
        confirmLabel="Release"
        loading={busy}
        onConfirm={() => void run(() => releaseWorkspaceStipend(workspaceId))}
      />
      <ConfirmationDialog
        open={pendingAction === "cancel"}
        onOpenChange={(open) => !open && setPendingAction(null)}
        title="Cancel this stipend record?"
        description="This cannot be undone -- there is only ever one stipend record per internship workspace."
        confirmLabel="Cancel stipend"
        destructive
        loading={busy}
        onConfirm={() => void run(() => cancelWorkspaceStipend(workspaceId))}
      />
    </div>
  );
}
