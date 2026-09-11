"use client";

import { useEffect, useId, useState } from "react";
import { CheckCircle2, Clock, Landmark } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FormError } from "@/components/auth/form-error";
import { ApiError } from "@/lib/api";
import {
  cancelLinkRequest,
  createLinkRequest,
  getMyLinkRequests,
  resolveInstitution,
} from "@/lib/institution-links";
import { LIVE_LINK_STATUSES, type InstitutionLinkRequest } from "@/types/institution-link";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; request: InstitutionLinkRequest | null };

/** Finds the request that currently occupies the student's one "live"
 * slot (PENDING or APPROVED) -- there can be at most one, enforced by
 * institution_link_requests_one_live_per_student_idx. Falls back to the
 * most recent non-live request (rejected/cancelled/removed) so the
 * student sees what happened last, or null if they've never requested. */
function currentRequest(requests: InstitutionLinkRequest[]): InstitutionLinkRequest | null {
  const live = requests.find((r) => LIVE_LINK_STATUSES.includes(r.status));
  if (live) return live;
  return requests[0] ?? null; // API returns newest-updated first
}

/**
 * Lets a student request to join their institution by its username, see
 * the status of that request, and cancel it while still pending. Once
 * approved, only the institution can unlink (components/institution/
 * students/institution-students-view.tsx) -- this card is read-only at
 * that point.
 */
export function InstitutionLinkCard() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [identifier, setIdentifier] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const inputId = useId();

  useEffect(() => {
    let cancelled = false;
    getMyLinkRequests()
      .then(({ requests }) => {
        if (!cancelled) setState({ status: "ready", request: currentRequest(requests) });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your institution link."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    const trimmed = identifier.trim();
    if (!trimmed || submitting) return;
    setSubmitting(true);
    try {
      const institution = await resolveInstitution(trimmed);
      const request = await createLinkRequest(institution.id);
      setState({ status: "ready", request });
      setIdentifier("");
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        setFormError("No institution account found with that username.");
      } else {
        setFormError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
      }
    } finally {
      setSubmitting(false);
    }
  }

  async function handleCancel(requestId: string) {
    setSubmitting(true);
    setFormError(null);
    try {
      const updated = await cancelLinkRequest(requestId);
      setState({ status: "ready", request: updated });
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not cancel the request.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Institution Link</CardTitle>
        <p className="text-xs text-muted-foreground">
          Link your account to your institution so it can see your progress, placements, and
          skills on its dashboard.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {state.status === "loading" ? (
          <p className="text-sm text-muted-foreground" aria-busy="true">
            Loading…
          </p>
        ) : null}

        {state.status === "error" ? (
          <div className="space-y-2">
            <FormError message={state.error.message} />
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
          </div>
        ) : null}

        {state.status === "ready" ? (
          <Body request={state.request} onCancel={handleCancel} submitting={submitting} />
        ) : null}

        {state.status === "ready" && (!state.request || !LIVE_LINK_STATUSES.includes(state.request.status)) ? (
          <form onSubmit={handleSubmit} className="space-y-2">
            <FormError message={formError} />
            <Label htmlFor={inputId}>Institution username</Label>
            <div className="flex gap-2">
              <Input
                id={inputId}
                value={identifier}
                onChange={(e) => setIdentifier(e.target.value)}
                placeholder="e.g. state_college"
                disabled={submitting}
              />
              <Button type="submit" disabled={submitting || !identifier.trim()}>
                {submitting ? "Sending…" : "Send Request"}
              </Button>
            </div>
            <p className="text-xs text-muted-foreground">
              Ask your institution&apos;s TPO for their SkillBridge username.
            </p>
          </form>
        ) : null}
      </CardContent>
    </Card>
  );
}

function Body({
  request,
  onCancel,
  submitting,
}: {
  request: InstitutionLinkRequest | null;
  onCancel: (requestId: string) => void;
  submitting: boolean;
}) {
  if (!request) return null;

  const name = request.institution_name?.trim() || "your institution";

  if (request.status === "PENDING") {
    return (
      <div className="flex items-center justify-between gap-3 rounded-lg border border-dashed px-3 py-2">
        <p className="flex items-center gap-1.5 text-sm">
          <Clock className="size-4 text-amber-600 dark:text-amber-400" aria-hidden="true" />
          Request sent to {name}. Waiting for approval.
        </p>
        <Button size="sm" variant="ghost" onClick={() => onCancel(request.id)} disabled={submitting}>
          Cancel
        </Button>
      </div>
    );
  }

  if (request.status === "APPROVED") {
    return (
      <p className="flex items-center gap-1.5 rounded-lg border border-dashed px-3 py-2 text-sm">
        <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" aria-hidden="true" />
        Linked to {name}.
      </p>
    );
  }

  // REJECTED / CANCELLED / REMOVED -- context only; the form below lets them try again.
  const note =
    request.status === "REJECTED"
      ? `Your request to join ${name} was rejected.`
      : request.status === "REMOVED"
        ? `You were unlinked from ${name}.`
        : `Your request to join ${name} was cancelled.`;

  return (
    <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
      <Landmark className="size-3.5 shrink-0" aria-hidden="true" />
      {note}
    </p>
  );
}
