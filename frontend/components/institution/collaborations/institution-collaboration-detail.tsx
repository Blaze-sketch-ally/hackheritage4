"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Handshake, Info } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { acceptCollaboration, getCollaboration, rejectCollaboration } from "@/lib/industry/collaborations";
import type { IndustryCollaboration } from "@/types/industry-collaboration";
import { CollaborationStatusBadge } from "@/components/industry/collaborations/collaboration-status-badge";
import { IndustryPartnerForm } from "@/components/institution/industry-partners/industry-partner-form";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; collaboration: IndustryCollaboration };

function formatDate(value: string | null): string {
  if (!value) return "—";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/**
 * Collaboration Detail (Phase 9, Part 6): reuses the SAME shared
 * GET /api/v1/collaborations/{id} endpoint the Industry side's own
 * detail page uses -- `require_collaboration_party` already scopes this
 * to either the initiating Industry account or the addressed
 * Institution, so a different institution's collaboration is a 404, not
 * a leak. No industry-private notes exist on this record to begin with
 * (industry_collaborations has no such column).
 */
export function InstitutionCollaborationDetail({ collaborationId }: { collaborationId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [confirming, setConfirming] = useState<"accept" | "reject" | null>(null);
  const [pending, setPending] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [partnerFormOpen, setPartnerFormOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getCollaboration(collaborationId)
      .then((collaboration) => {
        if (!cancelled) setState({ status: "ready", collaboration });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this collaboration."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [collaborationId, reloadKey]);

  async function runAction(action: "accept" | "reject") {
    setConfirming(null);
    setPending(true);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = action === "accept" ? await acceptCollaboration(collaborationId) : await rejectCollaboration(collaborationId);
      setState({ status: "ready", collaboration: updated });
      setActionSuccess(action === "accept" ? "Proposal accepted." : "Proposal rejected.");
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <Button variant="ghost" size="sm" render={<Link href="/institution/collaborations" />}>
        <ArrowLeft className="size-4" /> Back to Collaborations
      </Button>

      {state.status === "loading" ? <Loading label="Loading collaboration…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={
            state.error.status === 404 ? "This collaboration isn't visible to your institution." : state.error.message
          }
          onRetry={
            state.error.status !== 401 && state.error.status !== 404
              ? () => {
                  setState({ status: "loading" });
                  setReloadKey((k) => k + 1);
                }
              : undefined
          }
        />
      ) : null}

      {state.status === "ready" ? (
        <div className="space-y-6">
          <div className="flex items-start justify-between gap-3">
            <div>
              <h1 className="text-xl font-semibold">{state.collaboration.title}</h1>
              {state.collaboration.industry_name ? (
                <p className="text-sm text-muted-foreground">{state.collaboration.industry_name}</p>
              ) : null}
            </div>
            <CollaborationStatusBadge status={state.collaboration.status} />
          </div>

          <FormError message={actionError} />
          <FormSuccess message={actionSuccess} />

          <Card>
            <CardHeader>
              <CardTitle className="text-base">Details</CardTitle>
            </CardHeader>
            <CardContent className="space-y-4 text-sm">
              <p className="whitespace-pre-line text-muted-foreground">{state.collaboration.description}</p>
              <div className="grid grid-cols-2 gap-3 border-t pt-3 text-xs">
                <div>
                  <span className="text-muted-foreground">Created</span>
                  <p className="font-medium">{formatDate(state.collaboration.created_at)}</p>
                </div>
                <div>
                  <span className="text-muted-foreground">Last Updated</span>
                  <p className="font-medium">{formatDate(state.collaboration.updated_at)}</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {state.collaboration.status === "SENT" ? (
            <div className="flex flex-wrap items-center gap-2">
              <Button onClick={() => setConfirming("accept")} disabled={pending}>
                Accept
              </Button>
              <Button variant="ghost" onClick={() => setConfirming("reject")} disabled={pending}>
                Reject
              </Button>
            </div>
          ) : null}

          <Button variant="outline" size="sm" onClick={() => setPartnerFormOpen(true)}>
            <Handshake className="size-4" /> Add to Industry Partners
          </Button>

          <p className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            Adding this company as an Industry Partner is a separate, explicit action -- collaborations never
            automatically create a partner relationship.
          </p>

          {partnerFormOpen ? (
            <IndustryPartnerForm
              open={partnerFormOpen}
              onOpenChange={setPartnerFormOpen}
              presetCompanyId={state.collaboration.industry_id}
              presetCompanyName={state.collaboration.industry_name}
              defaultRelationshipType="COLLABORATION"
              onSaved={() => setPartnerFormOpen(false)}
            />
          ) : null}
        </div>
      ) : null}

      <ConfirmationDialog
        open={!!confirming}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={confirming === "accept" ? "Accept this collaboration proposal?" : "Reject this collaboration proposal?"}
        description={
          confirming === "accept"
            ? "The industry initiator will be notified you've agreed."
            : "This can't be undone."
        }
        confirmLabel={confirming === "accept" ? "Accept" : "Reject"}
        destructive={confirming === "reject"}
        loading={pending}
        onConfirm={() => confirming && runAction(confirming)}
      />
    </div>
  );
}
