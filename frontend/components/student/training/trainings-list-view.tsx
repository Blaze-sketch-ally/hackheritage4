"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, Building2, CalendarDays, CheckCircle2, GraduationCap, Inbox, MapPin, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { SearchBar } from "@/components/common/search-bar";
import { ApiError } from "@/lib/api";
import { listMyTrainingApplications, listTrainings, withdrawTrainingApplication } from "@/lib/student/training";
import { TRAINING_APPLICATION_STATUS_LABELS, type TrainingApplication } from "@/types/training-application";
import type { StudentTraining } from "@/types/student-training";

type Tab = "browse" | "mine";

type BrowseState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; trainings: StudentTraining[] };

type MineState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; applications: TrainingApplication[] };

function formatDate(value: string | null): string | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

const WITHDRAWABLE = new Set(["APPLIED"]);
const WORKSPACE_ELIGIBLE = new Set(["ACCEPTED", "COMPLETED"]);

export function TrainingsListView() {
  const [tab, setTab] = useState<Tab>("browse");
  const [search, setSearch] = useState("");
  const [browseState, setBrowseState] = useState<BrowseState>({ status: "loading" });
  const [mineState, setMineState] = useState<MineState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [mineReloadKey, setMineReloadKey] = useState(0);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [confirmWithdraw, setConfirmWithdraw] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listTrainings({ search }).then(
      ({ trainings }) => !cancelled && setBrowseState({ status: "ready", trainings }),
      (err) =>
        !cancelled &&
        setBrowseState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load training programs.",
        }),
    );
    return () => {
      cancelled = true;
    };
  }, [search, reloadKey]);

  useEffect(() => {
    if (tab !== "mine") return;
    let cancelled = false;
    listMyTrainingApplications().then(
      ({ applications }) => !cancelled && setMineState({ status: "ready", applications }),
      (err) =>
        !cancelled &&
        setMineState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load your applications.",
        }),
    );
    return () => {
      cancelled = true;
    };
  }, [tab, mineReloadKey]);

  async function handleWithdraw(id: string) {
    setConfirmWithdraw(null);
    setPendingId(id);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await withdrawTrainingApplication(id);
      setMineState((s) =>
        s.status === "ready"
          ? { ...s, applications: s.applications.map((a) => (a.id === id ? updated : a)) }
          : s,
      );
      setActionSuccess("Application withdrawn.");
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not withdraw. Please try again.");
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex gap-1.5">
          <Button variant={tab === "browse" ? "default" : "outline"} size="sm" onClick={() => setTab("browse")}>
            Browse
          </Button>
          <Button
            variant={tab === "mine" ? "default" : "outline"}
            size="sm"
            onClick={() => {
              setTab("mine");
              setMineState({ status: "loading" });
              setMineReloadKey((k) => k + 1);
            }}
          >
            My Applications
          </Button>
        </div>
        {tab === "browse" && (
          <SearchBar value={search} onChange={setSearch} placeholder="Search training programs…" />
        )}
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

      {tab === "browse" && (
        <>
          {browseState.status === "loading" && (
            <p className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
              Loading…
            </p>
          )}
          {browseState.status === "error" && (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
                <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
                <p className="text-sm text-muted-foreground">{browseState.message}</p>
                <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
                  <RefreshCw className="size-3.5" /> Try again
                </Button>
              </CardContent>
            </Card>
          )}
          {browseState.status === "ready" && browseState.trainings.length === 0 && (
            <EmptyState icon={Inbox} title="No training programs available" description="Check back soon for new programs." />
          )}
          {browseState.status === "ready" && browseState.trainings.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {browseState.trainings.map((t) => (
                <Card key={t.id} className="flex flex-col">
                  <CardHeader>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {t.location && (
                        <Badge variant="outline" className="gap-1">
                          <MapPin className="size-3" aria-hidden="true" />
                          {t.location}
                        </Badge>
                      )}
                      {t.has_applied && (
                        <Badge className="gap-1 bg-emerald-600 text-white hover:bg-emerald-600">
                          <CheckCircle2 className="size-3" aria-hidden="true" />
                          Applied
                        </Badge>
                      )}
                    </div>
                    <CardTitle className="text-base">{t.title}</CardTitle>
                    {t.industry.company_name && (
                      <p className="flex items-center gap-1 text-sm text-muted-foreground">
                        <Building2 className="size-3.5" aria-hidden="true" />
                        {t.industry.company_name}
                      </p>
                    )}
                  </CardHeader>
                  <CardContent className="flex-1 text-sm text-muted-foreground">
                    <p className="line-clamp-3">{t.description}</p>
                  </CardContent>
                  <CardFooter>
                    <Button className="w-full" render={<Link href={`/student/trainings/${t.id}`} />} nativeButton={false}>
                      <GraduationCap /> View Details
                    </Button>
                  </CardFooter>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      {tab === "mine" && (
        <>
          {mineState.status === "loading" && (
            <p className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
              Loading…
            </p>
          )}
          {mineState.status === "error" && (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
                <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
                <p className="text-sm text-muted-foreground">{mineState.message}</p>
              </CardContent>
            </Card>
          )}
          {mineState.status === "ready" && mineState.applications.length === 0 && (
            <EmptyState icon={Inbox} title="No applications yet" description="Apply to a training program to see it here." />
          )}
          {mineState.status === "ready" && mineState.applications.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2">
              {mineState.applications.map((a) => (
                <Card key={a.id}>
                  <CardContent className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium">{a.training?.title ?? "(training unavailable)"}</p>
                      <Badge variant="ghost">{TRAINING_APPLICATION_STATUS_LABELS[a.status]}</Badge>
                    </div>
                    {a.applied_at && (
                      <p className="flex items-center gap-1 text-xs text-muted-foreground">
                        <CalendarDays className="size-3.5" aria-hidden="true" /> Applied {formatDate(a.applied_at)}
                      </p>
                    )}
                    <div className="flex gap-2 pt-1">
                      <Button size="sm" variant="outline" render={<Link href={`/student/trainings/${a.training_id}`} />}>
                        View Training
                      </Button>
                      {WORKSPACE_ELIGIBLE.has(a.status) && (
                        <Button size="sm" render={<Link href={`/student/trainings/${a.training_id}/workspace`} />}>
                          Open Workspace
                        </Button>
                      )}
                      {WITHDRAWABLE.has(a.status) && (
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={pendingId === a.id}
                          onClick={() => setConfirmWithdraw(a.id)}
                        >
                          Withdraw
                        </Button>
                      )}
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}

      <ConfirmationDialog
        open={confirmWithdraw !== null}
        onOpenChange={(open) => !open && setConfirmWithdraw(null)}
        title="Withdraw this application?"
        description="You can't undo this. You may be able to re-apply if the program is still open."
        confirmLabel="Withdraw"
        destructive
        loading={pendingId !== null}
        onConfirm={() => confirmWithdraw && handleWithdraw(confirmWithdraw)}
      />
    </div>
  );
}
