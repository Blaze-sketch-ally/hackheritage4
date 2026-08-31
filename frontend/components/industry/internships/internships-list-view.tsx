"use client";

import { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { AlertCircle, Briefcase, Plus, RefreshCw, Search } from "lucide-react";
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
  archiveInternship,
  closeInternship,
  getInternships,
  publishInternship,
} from "@/lib/industry/internships";
import {
  INTERNSHIP_STATUSES,
  INTERNSHIP_STATUS_LABELS,
  type Internship,
} from "@/types/internship";
import { InternshipCard } from "@/components/industry/internships/internship-card";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; internships: Internship[] };

type LifecycleAction = "publish" | "close" | "archive";

const ACTION_COPY: Record<LifecycleAction, { title: string; description: string; confirm: string; destructive: boolean }> = {
  publish: {
    title: "Publish this internship?",
    description: "Students will be able to see and apply to it.",
    confirm: "Publish",
    destructive: false,
  },
  close: {
    title: "Close this internship?",
    description: "It stops accepting new applications. You can publish it again later.",
    confirm: "Close",
    destructive: false,
  },
  archive: {
    title: "Archive this internship?",
    description: "It's hidden from students and moved out of your active list. This can't be undone.",
    confirm: "Archive",
    destructive: true,
  },
};

const RUNNERS: Record<LifecycleAction, (id: string) => Promise<Internship>> = {
  publish: publishInternship,
  close: closeInternship,
  archive: archiveInternship,
};

export function InternshipsListView() {
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
    getInternships()
      .then(({ internships }) => {
        if (!cancelled) setState({ status: "ready", internships });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your internships."),
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
    return state.internships.filter((it) => {
      const matchesStatus = statusFilter === "all" || it.status === statusFilter;
      const matchesSearch = !query || it.title.toLowerCase().includes(query);
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
          ? { ...prev, internships: prev.internships.map((it) => (it.id === id ? updated : it)) }
          : prev,
      );
      setActionSuccess(
        action === "publish"
          ? "Internship published."
          : action === "close"
            ? "Internship closed."
            : "Internship archived.",
      );
    } catch (err) {
      setActionError(
        err instanceof ApiError
          ? err.message
          : "Something went wrong. Please try again.",
      );
    } finally {
      setPending(null);
    }
  }

  const statusOptions = [
    { value: "all", label: "All statuses" },
    ...INTERNSHIP_STATUSES.map((s) => ({ value: s, label: INTERNSHIP_STATUS_LABELS[s] })),
  ];

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Internships</h1>
          <p className="text-sm text-muted-foreground">
            Create and manage your internship opportunities.
          </p>
        </div>
        <Button render={<Link href="/industry/internships/create" />}>
          <Plus className="size-4" /> Create Internship
        </Button>
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading your internships…
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
                  : "Could not load your internships."}
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
        state.internships.length === 0 ? (
          <EmptyState
            icon={Briefcase}
            title="No internships yet"
            description="Create your first internship opportunity and save it as a draft."
            actionLabel="+ Create Internship"
            onAction={() => router.push("/industry/internships/create")}
          />
        ) : (
          <>
            <div className="flex flex-col gap-3 sm:flex-row">
              <SearchBar
                value={search}
                onChange={setSearch}
                placeholder="Search by title..."
                aria-label="Search internships"
              />
              <Filters
                value={statusFilter}
                onChange={setStatusFilter}
                options={statusOptions}
                aria-label="Filter by status"
              />
            </div>

            {visible.length === 0 ? (
              <EmptyState icon={Search} title="No internships match your filters" />
            ) : (
              <div className="space-y-3">
                {visible.map((internship) => (
                  <InternshipCard
                    key={internship.id}
                    internship={internship}
                    pending={pending?.id === internship.id}
                    onPublish={() => setConfirming({ id: internship.id, action: "publish" })}
                    onClose={() => setConfirming({ id: internship.id, action: "close" })}
                    onArchive={() => setConfirming({ id: internship.id, action: "archive" })}
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
