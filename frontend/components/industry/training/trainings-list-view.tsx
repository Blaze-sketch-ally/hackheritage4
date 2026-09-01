"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, GraduationCap, Plus, RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { Filters } from "@/components/common/filters";
import { SearchBar } from "@/components/common/search-bar";
import { ApiError } from "@/lib/api";
import { archiveTraining, closeTraining, getTrainings, publishTraining } from "@/lib/industry/training";
import { TRAINING_STATUSES, TRAINING_STATUS_LABELS, type IndustryTraining } from "@/types/industry-training";
import { TrainingCard } from "@/components/industry/training/training-card";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; trainings: IndustryTraining[] };

type LifecycleAction = "publish" | "close" | "archive";

const ACTION_COPY: Record<
  LifecycleAction,
  { title: string; description: string; confirm: string; destructive: boolean }
> = {
  publish: {
    title: "Publish this training record?",
    description: "Students will be able to see it.",
    confirm: "Publish",
    destructive: false,
  },
  close: {
    title: "Close this training record?",
    description: "It stops accepting new interest. You can publish it again later.",
    confirm: "Close",
    destructive: false,
  },
  archive: {
    title: "Archive this training record?",
    description: "It's hidden from students and moved out of your active list. This can't be undone.",
    confirm: "Archive",
    destructive: true,
  },
};

const RUNNERS: Record<LifecycleAction, (id: string) => Promise<IndustryTraining>> = {
  publish: publishTraining,
  close: closeTraining,
  archive: archiveTraining,
};

export function TrainingsListView() {
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
    getTrainings()
      .then(({ trainings }) => {
        if (!cancelled) setState({ status: "ready", trainings });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your training records."),
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
    return state.trainings.filter((training) => {
      const matchesStatus = statusFilter === "all" || training.status === statusFilter;
      const matchesSearch = !query || training.title.toLowerCase().includes(query);
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
          ? { ...prev, trainings: prev.trainings.map((t) => (t.id === id ? updated : t)) }
          : prev,
      );
      setActionSuccess(
        action === "publish"
          ? "Training published."
          : action === "close"
            ? "Training closed."
            : "Training archived.",
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
    ...TRAINING_STATUSES.map((s) => ({ value: s, label: TRAINING_STATUS_LABELS[s] })),
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Training</h1>
          <p className="text-sm text-muted-foreground">Create and manage your training programs.</p>
        </div>
        <Button render={<Link href="/industry/training/create" />}>
          <Plus className="size-4" /> Create Training
        </Button>
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading your training records…
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
                  : "Could not load your training records."}
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
        state.trainings.length === 0 ? (
          <EmptyState
            icon={GraduationCap}
            title="No training records yet"
            description="Create your first training program and save it as a draft."
            actionLabel="+ Create Training"
            onAction={() => router.push("/industry/training/create")}
          />
        ) : (
          <>
            <div className="flex flex-col gap-3 sm:flex-row">
              <SearchBar
                value={search}
                onChange={setSearch}
                placeholder="Search by title..."
                aria-label="Search training"
              />
              <Filters
                value={statusFilter}
                onChange={setStatusFilter}
                options={statusOptions}
                aria-label="Filter by status"
              />
            </div>

            {visible.length === 0 ? (
              <EmptyState icon={Search} title="No training records match your filters" />
            ) : (
              <div className="space-y-3">
                {visible.map((training) => (
                  <TrainingCard
                    key={training.id}
                    training={training}
                    pending={pending?.id === training.id}
                    onPublish={() => setConfirming({ id: training.id, action: "publish" })}
                    onClose={() => setConfirming({ id: training.id, action: "close" })}
                    onArchive={() => setConfirming({ id: training.id, action: "archive" })}
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
