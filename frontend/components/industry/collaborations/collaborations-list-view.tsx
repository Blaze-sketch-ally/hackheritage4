"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, Network, Plus, RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { Filters } from "@/components/common/filters";
import { SearchBar } from "@/components/common/search-bar";
import { ApiError } from "@/lib/api";
import {
  activateCollaboration,
  cancelCollaboration,
  completeCollaboration,
  getCollaborations,
  sendCollaboration,
} from "@/lib/industry/collaborations";
import {
  COLLABORATION_STATUSES,
  COLLABORATION_STATUS_LABELS,
  type IndustryCollaboration,
} from "@/types/industry-collaboration";
import { CollaborationCard } from "@/components/industry/collaborations/collaboration-card";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; collaborations: IndustryCollaboration[] };

type LifecycleAction = "send" | "activate" | "complete" | "cancel";

const ACTION_COPY: Record<
  LifecycleAction,
  { title: string; description: string; confirm: string; destructive: boolean; done: string }
> = {
  send: {
    title: "Send this proposal?",
    description: "The recipient will be able to see it and respond.",
    confirm: "Send",
    destructive: false,
    done: "Proposal sent.",
  },
  activate: {
    title: "Activate this collaboration?",
    description: "This marks the collaboration as formally underway.",
    confirm: "Activate",
    destructive: false,
    done: "Collaboration activated.",
  },
  complete: {
    title: "Mark this collaboration as completed?",
    description: "This can't be undone.",
    confirm: "Complete",
    destructive: false,
    done: "Collaboration completed.",
  },
  cancel: {
    title: "Cancel this collaboration?",
    description: "This can't be undone.",
    confirm: "Cancel Collaboration",
    destructive: true,
    done: "Collaboration cancelled.",
  },
};

const RUNNERS: Record<LifecycleAction, (id: string) => Promise<IndustryCollaboration>> = {
  send: sendCollaboration,
  activate: activateCollaboration,
  complete: completeCollaboration,
  cancel: cancelCollaboration,
};

export function CollaborationsListView() {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");

  const [pending, setPending] = useState<{ id: string; action: LifecycleAction } | null>(null);
  const [confirming, setConfirming] = useState<{ id: string; action: LifecycleAction } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getCollaborations()
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

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  const visible = useMemo(() => {
    if (state.status !== "ready") return [];
    const query = search.trim().toLowerCase();
    return state.collaborations.filter((c) => {
      const matchesStatus = statusFilter === "all" || c.status === statusFilter;
      const matchesSearch = !query || c.title.toLowerCase().includes(query);
      return matchesStatus && matchesSearch;
    });
  }, [state, search, statusFilter]);

  async function runAction(id: string, action: LifecycleAction) {
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
      setActionError(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setPending(null);
    }
  }

  const statusOptions = [
    { value: "all", label: "All statuses" },
    ...COLLABORATION_STATUSES.map((s) => ({ value: s, label: COLLABORATION_STATUS_LABELS[s] })),
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Collaborations</h1>
          <p className="text-sm text-muted-foreground">
            Propose and manage collaborations with Faculty and Institutions.
          </p>
        </div>
        <Button render={<Link href="/industry/collaborations/create" />}>
          <Plus className="size-4" /> Create Collaboration
        </Button>
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading your collaborations…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {state.error.status === 401
                  ? "Your session has expired. Please sign in again."
                  : "Could not load your collaborations."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status !== 401 ? (
              <Button variant="outline" size="sm" onClick={reload}>
                <RefreshCw className="size-3.5" /> Try again
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? (
        state.collaborations.length === 0 ? (
          <EmptyState
            icon={Network}
            title="No collaborations yet"
            description="Propose your first collaboration and save it as a draft."
            actionLabel="+ Create Collaboration"
            onAction={() => router.push("/industry/collaborations/create")}
          />
        ) : (
          <>
            <div className="flex flex-col gap-3 sm:flex-row">
              <SearchBar
                value={search}
                onChange={setSearch}
                placeholder="Search by title..."
                aria-label="Search collaborations"
              />
              <Filters
                value={statusFilter}
                onChange={setStatusFilter}
                options={statusOptions}
                aria-label="Filter by status"
              />
            </div>

            {visible.length === 0 ? (
              <EmptyState icon={Search} title="No collaborations match your filters" />
            ) : (
              <div className="space-y-3">
                {visible.map((collaboration) => (
                  <CollaborationCard
                    key={collaboration.id}
                    collaboration={collaboration}
                    pending={pending?.id === collaboration.id}
                    onSend={() => setConfirming({ id: collaboration.id, action: "send" })}
                    onActivate={() => setConfirming({ id: collaboration.id, action: "activate" })}
                    onComplete={() => setConfirming({ id: collaboration.id, action: "complete" })}
                    onCancel={() => setConfirming({ id: collaboration.id, action: "cancel" })}
                  />
                ))}
              </div>
            )}
          </>
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
