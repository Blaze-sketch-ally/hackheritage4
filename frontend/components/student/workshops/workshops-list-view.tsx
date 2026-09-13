"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, Building2, CalendarDays, CheckCircle2, Inbox, MapPin, Presentation, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { SearchBar } from "@/components/common/search-bar";
import { ApiError } from "@/lib/api";
import { listMyWorkshopApplications, listWorkshops, withdrawWorkshopApplication } from "@/lib/student/workshops";
import { WORKSHOP_APPLICATION_STATUS_LABELS, type WorkshopApplication } from "@/types/workshop-application";
import type { StudentWorkshop } from "@/types/student-workshop";

type Tab = "browse" | "mine";

type BrowseState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; workshops: StudentWorkshop[] };

type MineState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; applications: WorkshopApplication[] };

function formatDate(value: string | null): string | null {
  if (!value) return null;
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

const WITHDRAWABLE = new Set(["APPLIED"]);
const WORKSPACE_ELIGIBLE = new Set(["ACCEPTED", "COMPLETED"]);

export function WorkshopsListView() {
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
    listWorkshops({ search }).then(
      ({ workshops }) => !cancelled && setBrowseState({ status: "ready", workshops }),
      (err) =>
        !cancelled &&
        setBrowseState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load workshops.",
        }),
    );
    return () => {
      cancelled = true;
    };
  }, [search, reloadKey]);

  useEffect(() => {
    if (tab !== "mine") return;
    let cancelled = false;
    listMyWorkshopApplications().then(
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
      const updated = await withdrawWorkshopApplication(id);
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
          <SearchBar value={search} onChange={setSearch} placeholder="Search workshops…" />
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
          {browseState.status === "ready" && browseState.workshops.length === 0 && (
            <EmptyState icon={Inbox} title="No workshops available" description="Check back soon for new workshops." />
          )}
          {browseState.status === "ready" && browseState.workshops.length > 0 && (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {browseState.workshops.map((w) => (
                <Card key={w.id} className="flex flex-col">
                  <CardHeader>
                    <div className="flex flex-wrap items-center gap-1.5">
                      {w.location && (
                        <Badge variant="outline" className="gap-1">
                          <MapPin className="size-3" aria-hidden="true" />
                          {w.location}
                        </Badge>
                      )}
                      {w.has_applied && (
                        <Badge className="gap-1 bg-emerald-600 text-white hover:bg-emerald-600">
                          <CheckCircle2 className="size-3" aria-hidden="true" />
                          Applied
                        </Badge>
                      )}
                    </div>
                    <CardTitle className="text-base">{w.title}</CardTitle>
                    {w.industry.company_name && (
                      <p className="flex items-center gap-1 text-sm text-muted-foreground">
                        <Building2 className="size-3.5" aria-hidden="true" />
                        {w.industry.company_name}
                      </p>
                    )}
                  </CardHeader>
                  <CardContent className="flex-1 text-sm text-muted-foreground">
                    <p className="line-clamp-3">{w.description}</p>
                  </CardContent>
                  <CardFooter>
                    <Button className="w-full" render={<Link href={`/student/workshops/${w.id}`} />} nativeButton={false}>
                      <Presentation /> View Details
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
            <EmptyState icon={Inbox} title="No applications yet" description="Apply to a workshop to see it here." />
          )}
          {mineState.status === "ready" && mineState.applications.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2">
              {mineState.applications.map((a) => (
                <Card key={a.id}>
                  <CardContent className="space-y-2">
                    <div className="flex items-start justify-between gap-2">
                      <p className="font-medium">{a.workshop?.title ?? "(workshop unavailable)"}</p>
                      <Badge variant="ghost">{WORKSHOP_APPLICATION_STATUS_LABELS[a.status]}</Badge>
                    </div>
                    {a.applied_at && (
                      <p className="flex items-center gap-1 text-xs text-muted-foreground">
                        <CalendarDays className="size-3.5" aria-hidden="true" /> Applied {formatDate(a.applied_at)}
                      </p>
                    )}
                    <div className="flex gap-2 pt-1">
                      <Button
                        size="sm"
                        variant="outline"
                        render={<Link href={`/student/workshops/${a.workshop_id}`} />}
                      >
                        View Workshop
                      </Button>
                      {WORKSPACE_ELIGIBLE.has(a.status) && (
                        <Button size="sm" render={<Link href={`/student/workshops/${a.workshop_id}/workspace`} />}>
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
        description="You can't undo this. You may be able to re-apply if the workshop is still open."
        confirmLabel="Withdraw"
        destructive
        loading={pendingId !== null}
        onConfirm={() => confirmWithdraw && handleWithdraw(confirmWithdraw)}
      />
    </div>
  );
}
