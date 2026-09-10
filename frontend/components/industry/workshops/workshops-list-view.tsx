"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, Presentation, Plus, RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { Filters } from "@/components/common/filters";
import { SearchBar } from "@/components/common/search-bar";
import { ApiError } from "@/lib/api";
import { archiveWorkshop, closeWorkshop, getWorkshops, publishWorkshop } from "@/lib/industry/workshops";
import { WORKSHOP_STATUSES, WORKSHOP_STATUS_LABELS, type IndustryWorkshop } from "@/types/industry-workshop";
import { WorkshopCard } from "@/components/industry/workshops/workshop-card";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; workshops: IndustryWorkshop[] };

type LifecycleAction = "publish" | "close" | "archive";

const ACTION_COPY: Record<
  LifecycleAction,
  { title: string; description: string; confirm: string; destructive: boolean }
> = {
  publish: {
    title: "Publish this workshop?",
    description: "Students will be able to see it.",
    confirm: "Publish",
    destructive: false,
  },
  close: {
    title: "Close this workshop?",
    description: "It stops accepting new interest. You can publish it again later.",
    confirm: "Close",
    destructive: false,
  },
  archive: {
    title: "Archive this workshop?",
    description: "It's hidden from students and moved out of your active list. This can't be undone.",
    confirm: "Archive",
    destructive: true,
  },
};

const RUNNERS: Record<LifecycleAction, (id: string) => Promise<IndustryWorkshop>> = {
  publish: publishWorkshop,
  close: closeWorkshop,
  archive: archiveWorkshop,
};

export function WorkshopsListView() {
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
    getWorkshops()
      .then(({ workshops }) => {
        if (!cancelled) setState({ status: "ready", workshops });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your workshops."),
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
    return state.workshops.filter((workshop) => {
      const matchesStatus = statusFilter === "all" || workshop.status === statusFilter;
      const matchesSearch = !query || workshop.title.toLowerCase().includes(query);
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
          ? { ...prev, workshops: prev.workshops.map((w) => (w.id === id ? updated : w)) }
          : prev,
      );
      setActionSuccess(
        action === "publish"
          ? "Workshop published."
          : action === "close"
            ? "Workshop closed."
            : "Workshop archived.",
      );
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
    ...WORKSHOP_STATUSES.map((s) => ({ value: s, label: WORKSHOP_STATUS_LABELS[s] })),
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Workshops</h1>
          <p className="text-sm text-muted-foreground">Create and manage your workshops.</p>
        </div>
        <Button render={<Link href="/industry/workshops/create" />}>
          <Plus className="size-4" /> Create Workshop
        </Button>
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading your workshops…
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
                  : "Could not load your workshops."}
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
        state.workshops.length === 0 ? (
          <EmptyState
            icon={Presentation}
            title="No workshops yet"
            description="Create your first workshop and save it as a draft."
            actionLabel="+ Create Workshop"
            onAction={() => router.push("/industry/workshops/create")}
          />
        ) : (
          <>
            <div className="flex flex-col gap-3 sm:flex-row">
              <SearchBar
                value={search}
                onChange={setSearch}
                placeholder="Search by title..."
                aria-label="Search workshops"
              />
              <Filters
                value={statusFilter}
                onChange={setStatusFilter}
                options={statusOptions}
                aria-label="Filter by status"
              />
            </div>

            {visible.length === 0 ? (
              <EmptyState icon={Search} title="No workshops match your filters" />
            ) : (
              <div className="space-y-3">
                {visible.map((workshop) => (
                  <WorkshopCard
                    key={workshop.id}
                    workshop={workshop}
                    pending={pending?.id === workshop.id}
                    onPublish={() => setConfirming({ id: workshop.id, action: "publish" })}
                    onClose={() => setConfirming({ id: workshop.id, action: "close" })}
                    onArchive={() => setConfirming({ id: workshop.id, action: "archive" })}
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
