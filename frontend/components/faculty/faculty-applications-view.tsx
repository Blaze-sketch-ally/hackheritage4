"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Check, Loader2, RefreshCw, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
// Reuses the existing Industry-collaboration API client as-is: the
// underlying endpoints (/api/v1/collaborations/incoming, /accept,
// /reject) already serve the FACULTY-as-recipient side of
// industry_collaborations (require_collaboration_recipient allows
// FACULTY/INSTITUTION) -- see backend/app/api/industry_collaborations.py.
// There is no separate "Faculty applies to a posting" mechanism anywhere
// in the current data model (industry_projects/training/workshops/
// mentorship each explicitly have no application/matching flow yet, per
// their own migration headers) -- industry_collaborations, a real,
// already-authorized, already-tested Faculty-facing engagement record,
// is the closest existing entity and is reused rather than duplicated
// with a new table. "Applications" here means "collaboration requests
// Industry has sent you", made explicit in the page copy rather than
// implied.
import { acceptCollaboration, getIncomingCollaborations, rejectCollaboration } from "@/lib/industry/collaborations";
import { COLLABORATION_STATUS_LABELS, type IndustryCollaboration } from "@/types/industry-collaboration";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; collaborations: IndustryCollaboration[] };

export function FacultyApplicationsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [actioningId, setActioningId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { collaborations } = await getIncomingCollaborations();
        if (cancelled) return;
        setState({ status: "ready", collaborations });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load your applications.",
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  async function handleRespond(id: string, action: "accept" | "reject") {
    setActioningId(id);
    setActionError(null);
    try {
      const updated = action === "accept" ? await acceptCollaboration(id) : await rejectCollaboration(id);
      setState((prev) =>
        prev.status === "ready"
          ? { ...prev, collaborations: prev.collaborations.map((c) => (c.id === id ? updated : c)) }
          : prev,
      );
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not update this application.");
    } finally {
      setActioningId(null);
    }
  }

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading your applications…
        </CardContent>
      </Card>
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <p className="font-medium">{state.message}</p>
          <Button size="sm" onClick={() => setReloadKey((k) => k + 1)}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { collaborations } = state;

  if (collaborations.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          No collaboration requests from Industry yet.
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-3">
      {actionError && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="size-3.5 shrink-0" /> {actionError}
        </p>
      )}
      {collaborations.map((c) => {
        const busy = actioningId === c.id;
        return (
          <Card key={c.id}>
            <CardContent className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
              <div className="min-w-0">
                <p className="font-medium">{c.title}</p>
                <p className="text-sm text-muted-foreground">
                  {c.industry_name ?? "An industry partner"} ·{" "}
                  {c.created_at ? new Date(c.created_at).toLocaleDateString() : "—"}
                </p>
              </div>
              <div className="flex shrink-0 items-center gap-2">
                <StatusBadge status={c.status} />
                {c.status === "SENT" && (
                  <div className="flex gap-1.5">
                    <Button size="sm" disabled={busy} onClick={() => void handleRespond(c.id, "accept")}>
                      <Check className="size-3.5" /> Accept
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      disabled={busy}
                      onClick={() => void handleRespond(c.id, "reject")}
                    >
                      <X className="size-3.5" /> Reject
                    </Button>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }: { status: IndustryCollaboration["status"] }) {
  const label = COLLABORATION_STATUS_LABELS[status];
  if (status === "ACCEPTED" || status === "ACTIVE") {
    return <Badge className="bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500">{label}</Badge>;
  }
  if (status === "REJECTED" || status === "CANCELLED") return <Badge variant="destructive">{label}</Badge>;
  if (status === "COMPLETED") return <Badge variant="secondary">{label}</Badge>;
  return <Badge variant="outline">{label}</Badge>;
}
