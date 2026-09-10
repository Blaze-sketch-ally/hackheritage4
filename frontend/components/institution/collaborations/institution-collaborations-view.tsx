"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Inbox, Search } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { acceptCollaboration, getIncomingCollaborations, rejectCollaboration } from "@/lib/industry/collaborations";
import { COLLABORATION_STATUS_LABELS, type IndustryCollaboration } from "@/types/industry-collaboration";
import { CollaborationStatusBadge } from "@/components/industry/collaborations/collaboration-status-badge";

const ALL = "__all__";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; collaborations: IndustryCollaboration[] };

type RecipientAction = "accept" | "reject";

const ACTION_COPY: Record<
  RecipientAction,
  { title: string; description: string; confirm: string; destructive: boolean; done: string }
> = {
  accept: {
    title: "Accept this collaboration proposal?",
    description: "The industry initiator will be notified you've agreed.",
    confirm: "Accept",
    destructive: false,
    done: "Proposal accepted.",
  },
  reject: {
    title: "Reject this collaboration proposal?",
    description: "This can't be undone.",
    confirm: "Reject",
    destructive: true,
    done: "Proposal rejected.",
  },
};

const RUNNERS: Record<RecipientAction, (id: string) => Promise<IndustryCollaboration>> = {
  accept: acceptCollaboration,
  reject: rejectCollaboration,
};

function formatDate(value: string | null): string {
  if (!value) return "—";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

const SECTIONS: { key: string; title: string; statuses: IndustryCollaboration["status"][] }[] = [
  { key: "pending", title: "Pending Requests", statuses: ["SENT"] },
  { key: "active", title: "Active Collaborations", statuses: ["ACCEPTED", "ACTIVE"] },
  { key: "completed", title: "Completed Collaborations", statuses: ["COMPLETED"] },
  { key: "other", title: "Other", statuses: ["REJECTED", "CANCELLED"] },
];

/**
 * The Institution-side Collaborations workspace (Phase 9): reuses the
 * EXISTING industry_collaborations bilateral proposal workflow verbatim
 * (lib/industry/collaborations.ts, the same shared
 * /api/v1/collaborations/incoming|accept|reject endpoints
 * RecipientCollaborationsView already uses for Faculty) -- grouped into
 * sections by real status, with search/filter added on top. No new
 * lifecycle, no new backend. Institution ownership/authorization is
 * unchanged: only a SENT proposal can be accepted/rejected, enforced
 * server-side regardless of what this UI shows.
 */
export function InstitutionCollaborationsView() {
  const searchParams = useSearchParams();
  const initialSearch = searchParams.get("company") ?? "";

  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [search, setSearch] = useState(initialSearch);
  const [statusFilter, setStatusFilter] = useState(ALL);

  const [pending, setPending] = useState<{ id: string; action: RecipientAction } | null>(null);
  const [confirming, setConfirming] = useState<{ id: string; action: RecipientAction } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getIncomingCollaborations()
      .then(({ collaborations }) => {
        if (!cancelled) setState({ status: "ready", collaborations });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your collaborations."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const filtered = useMemo(() => {
    if (state.status !== "ready") return [];
    let rows = state.collaborations;
    if (statusFilter !== ALL) rows = rows.filter((c) => c.status === statusFilter);
    const needle = search.trim().toLowerCase();
    if (needle) {
      rows = rows.filter(
        (c) => c.title.toLowerCase().includes(needle) || (c.industry_name ?? "").toLowerCase().includes(needle),
      );
    }
    return rows;
  }, [state, search, statusFilter]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function runAction(id: string, action: RecipientAction) {
    setConfirming(null);
    setPending({ id, action });
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await RUNNERS[action](id);
      setState((prev) =>
        prev.status === "ready"
          ? { ...prev, collaborations: prev.collaborations.map((c) => (c.id === id ? updated : c)) }
          : prev,
      );
      setActionSuccess(ACTION_COPY[action].done);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setPending(null);
    }
  }

  const hasAny = state.status === "ready" && state.collaborations.length > 0;

  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Collaborations</h1>
        <p className="text-sm text-muted-foreground">Collaboration proposals from Industry partners.</p>
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

      {state.status === "loading" ? <Loading label="Loading your collaborations…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={
            state.error.status === 401 ? "Your session has expired. Please sign in again." : state.error.message
          }
          onRetry={state.error.status !== 401 ? reload : undefined}
        />
      ) : null}

      {state.status === "ready" ? (
        hasAny ? (
          <>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="relative w-full sm:max-w-xs">
                <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by company or title..."
                  className="pl-8"
                  aria-label="Search collaborations"
                />
              </div>
              <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v ?? ALL)}>
                <SelectTrigger className="w-full sm:w-44" aria-label="Filter by status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All statuses</SelectItem>
                  {Object.entries(COLLABORATION_STATUS_LABELS)
                    .filter(([s]) => s !== "DRAFT")
                    .map(([s, label]) => (
                      <SelectItem key={s} value={s}>
                        {label}
                      </SelectItem>
                    ))}
                </SelectContent>
              </Select>
            </div>

            {filtered.length === 0 ? (
              <EmptyState icon={Search} title="No collaborations match your filters" />
            ) : statusFilter !== ALL ? (
              <CollaborationTable
                collaborations={filtered}
                pending={pending}
                onAccept={(id) => setConfirming({ id, action: "accept" })}
                onReject={(id) => setConfirming({ id, action: "reject" })}
              />
            ) : (
              <div className="space-y-6">
                {SECTIONS.map((section) => {
                  const rows = filtered.filter((c) => section.statuses.includes(c.status));
                  if (rows.length === 0) return null;
                  return (
                    <div key={section.key} className="space-y-2">
                      <h2 className="text-sm font-semibold text-muted-foreground">
                        {section.title} ({rows.length})
                      </h2>
                      <CollaborationTable
                        collaborations={rows}
                        pending={pending}
                        onAccept={(id) => setConfirming({ id, action: "accept" })}
                        onReject={(id) => setConfirming({ id, action: "reject" })}
                      />
                    </div>
                  );
                })}
              </div>
            )}
          </>
        ) : (
          <EmptyState
            icon={Inbox}
            title="No collaboration proposals yet"
            description="Proposals sent to you by Industry partners will appear here."
          />
        )
      ) : null}

      <ConfirmationDialog
        open={!!confirming}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={confirming ? ACTION_COPY[confirming.action].title : ""}
        description={confirming ? ACTION_COPY[confirming.action].description : undefined}
        confirmLabel={confirming ? ACTION_COPY[confirming.action].confirm : "Confirm"}
        destructive={confirming ? ACTION_COPY[confirming.action].destructive : false}
        loading={!!pending}
        onConfirm={() => confirming && runAction(confirming.id, confirming.action)}
      />
    </div>
  );
}

function CollaborationTable({
  collaborations,
  pending,
  onAccept,
  onReject,
}: {
  collaborations: IndustryCollaboration[];
  pending: { id: string; action: RecipientAction } | null;
  onAccept: (id: string) => void;
  onReject: (id: string) => void;
}) {
  return (
    <div className="space-y-2">
      {collaborations.map((c) => (
        <Card key={c.id}>
          <CardContent className="space-y-2">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0 space-y-1">
                <Link href={`/institution/collaborations/${c.id}`} className="font-medium hover:underline">
                  {c.title}
                </Link>
                {c.industry_name ? <p className="truncate text-sm">{c.industry_name}</p> : null}
                <p className="text-xs text-muted-foreground">
                  Created {formatDate(c.created_at)} · Updated {formatDate(c.updated_at)}
                </p>
              </div>
              <CollaborationStatusBadge status={c.status} />
            </div>
            {c.status === "SENT" ? (
              <div className="flex flex-wrap items-center gap-2 pt-1">
                <Button size="sm" onClick={() => onAccept(c.id)} disabled={pending?.id === c.id}>
                  Accept
                </Button>
                <Button size="sm" variant="ghost" onClick={() => onReject(c.id)} disabled={pending?.id === c.id}>
                  Reject
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
