"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Check, Loader2, Plus, RefreshCw, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { EOI_STATUS_LABELS, type FacultyOpportunityExpression } from "@/types/faculty-opportunity-expression";
import { ENGAGEMENT_STATUS_LABELS, type EngagementStatus, type FacultyEngagement } from "@/types/faculty-engagement";
import type {
  FacultyOpportunityPosting,
  FacultyOpportunityPostingInput,
  FacultyOpportunityPostingListResponse,
} from "@/types/faculty-opportunity-posting";

/**
 * Owner-agnostic Faculty-opportunity management surface. Used by both
 * IndustryFacultyOpportunitiesView and InstitutionFacultyOpportunitiesView
 * -- the UI is identical for both owner types (same shape, same
 * lifecycle), so it is shared here rather than duplicated; the backend
 * stays deliberately duplicated per-owner (industry_faculty_opportunity_
 * service.py / institution_faculty_opportunity_service.py) for the
 * no-dynamic-SQL reasons documented there. Passing functions as props is
 * ordinary React composition, not the polymorphic-ID pattern the
 * database schema itself avoids.
 *
 * This is the minimum usable vertical slice, not a new dashboard: list,
 * create, edit-while-draft, publish, close, and review EOIs. No
 * pagination, no search, no bulk actions.
 */

export interface FacultyOpportunityManagementApi {
  listOpportunities: () => Promise<FacultyOpportunityPostingListResponse>;
  createOpportunity: (input: FacultyOpportunityPostingInput) => Promise<FacultyOpportunityPosting>;
  updateOpportunity: (id: string, input: Partial<FacultyOpportunityPostingInput>) => Promise<FacultyOpportunityPosting>;
  publishOpportunity: (id: string) => Promise<FacultyOpportunityPosting>;
  closeOpportunity: (id: string) => Promise<FacultyOpportunityPosting>;
  listEois: () => Promise<{ expressions: FacultyOpportunityExpression[] }>;
  reviewEoi: (
    eoiId: string,
    status: "UNDER_REVIEW" | "ACCEPTED" | "REJECTED",
    reviewerNote?: string,
  ) => Promise<FacultyOpportunityExpression>;
  updateEngagementStatus: (
    engagementId: string,
    status: Extract<EngagementStatus, "ACTIVE" | "COMPLETED" | "CANCELLED">,
  ) => Promise<FacultyEngagement>;
}

type OpportunityState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; opportunities: FacultyOpportunityPosting[] };

type EoiState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; expressions: FacultyOpportunityExpression[] };

export function FacultyOpportunityManagementView({ api: managementApi }: { api: FacultyOpportunityManagementApi }) {
  return (
    <Tabs defaultValue="opportunities">
      <TabsList>
        <TabsTrigger value="opportunities">My Faculty Opportunities</TabsTrigger>
        <TabsTrigger value="eois">Expressions of Interest</TabsTrigger>
      </TabsList>
      <TabsContent value="opportunities" className="pt-4">
        <OpportunitiesPanel api={managementApi} />
      </TabsContent>
      <TabsContent value="eois" className="pt-4">
        <EoisPanel api={managementApi} />
      </TabsContent>
    </Tabs>
  );
}

function OpportunitiesPanel({ api: managementApi }: { api: FacultyOpportunityManagementApi }) {
  const [state, setState] = useState<OpportunityState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [createOpen, setCreateOpen] = useState(false);
  const [editing, setEditing] = useState<FacultyOpportunityPosting | null>(null);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { opportunities } = await managementApi.listOpportunities();
        if (cancelled) return;
        setState({ status: "ready", opportunities });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load your Faculty opportunities.",
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [managementApi, reloadKey]);

  function refresh() {
    setReloadKey((k) => k + 1);
  }

  async function handlePublish(id: string) {
    setBusyId(id);
    setActionError(null);
    try {
      await managementApi.publishOpportunity(id);
      refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not publish the opportunity.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleClose(id: string) {
    setBusyId(id);
    setActionError(null);
    try {
      await managementApi.closeOpportunity(id);
      refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not close the opportunity.");
    } finally {
      setBusyId(null);
    }
  }

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading your Faculty opportunities…
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
          <Button size="sm" onClick={refresh}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { opportunities } = state;

  return (
    <div className="flex flex-col gap-4">
      <div className="flex justify-end">
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="size-3.5" /> New Faculty Opportunity
        </Button>
      </div>

      {actionError && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="size-3.5 shrink-0" /> {actionError}
        </p>
      )}

      {opportunities.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            You haven&apos;t created any Faculty opportunities yet.
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {opportunities.map((o) => (
            <Card key={o.id}>
              <CardContent className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
                <div className="min-w-0">
                  <p className="font-medium">{o.title}</p>
                  <p className="line-clamp-1 text-sm text-muted-foreground">{o.description}</p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <StatusBadge status={o.status} />
                  {o.status === "DRAFT" && (
                    <>
                      <Button size="sm" variant="outline" onClick={() => setEditing(o)}>
                        Edit
                      </Button>
                      <Button size="sm" disabled={busyId === o.id} onClick={() => void handlePublish(o.id)}>
                        Publish
                      </Button>
                    </>
                  )}
                  {o.status === "PUBLISHED" && (
                    <Button size="sm" variant="outline" disabled={busyId === o.id} onClick={() => void handleClose(o.id)}>
                      Close
                    </Button>
                  )}
                  {o.status === "CLOSED" && (
                    <Button size="sm" disabled={busyId === o.id} onClick={() => void handlePublish(o.id)}>
                      Re-publish
                    </Button>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <OpportunityFormDialog
        mode="create"
        open={createOpen}
        onClose={() => setCreateOpen(false)}
        onSaved={() => {
          setCreateOpen(false);
          refresh();
        }}
        onSubmit={(input) => managementApi.createOpportunity(input)}
      />
      <OpportunityFormDialog
        key={editing?.id ?? "none"}
        mode="edit"
        open={editing !== null}
        initial={editing ?? undefined}
        onClose={() => setEditing(null)}
        onSaved={() => {
          setEditing(null);
          refresh();
        }}
        onSubmit={(input) => managementApi.updateOpportunity(editing!.id, input)}
      />
    </div>
  );
}

function OpportunityFormDialog({
  mode,
  open,
  initial,
  onClose,
  onSaved,
  onSubmit,
}: {
  mode: "create" | "edit";
  open: boolean;
  initial?: FacultyOpportunityPosting;
  onClose: () => void;
  onSaved: () => void;
  onSubmit: (input: FacultyOpportunityPostingInput) => Promise<FacultyOpportunityPosting>;
}) {
  const [title, setTitle] = useState(initial?.title ?? "");
  const [description, setDescription] = useState(initial?.description ?? "");
  const [location, setLocation] = useState(initial?.location ?? "");
  const [capacity, setCapacity] = useState(initial?.capacity?.toString() ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit() {
    setSaving(true);
    setError(null);
    try {
      await onSubmit({
        title,
        description,
        location: location || null,
        capacity: capacity.trim() === "" ? null : Number(capacity),
      });
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the opportunity.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={(next) => !next && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{mode === "create" ? "New Faculty opportunity" : "Edit draft opportunity"}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fo-title">Title</Label>
            <Input id="fo-title" value={title} onChange={(e) => setTitle(e.target.value)} />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="fo-description">Description</Label>
            <Textarea id="fo-description" rows={4} value={description} onChange={(e) => setDescription(e.target.value)} />
          </div>
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fo-location">Location</Label>
              <Input id="fo-location" value={location} onChange={(e) => setLocation(e.target.value)} />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="fo-capacity">Capacity</Label>
              <Input id="fo-capacity" type="number" min={1} value={capacity} onChange={(e) => setCapacity(e.target.value)} />
            </div>
          </div>
          {error && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertCircle className="size-3.5 shrink-0" /> {error}
            </p>
          )}
        </div>
        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>Cancel</DialogClose>
          <Button onClick={() => void handleSubmit()} disabled={saving || !title || !description}>
            {saving ? <Loader2 className="size-3.5 animate-spin" /> : null}
            Save
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

function EoisPanel({ api: managementApi }: { api: FacultyOpportunityManagementApi }) {
  const [state, setState] = useState<EoiState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { expressions } = await managementApi.listEois();
        if (cancelled) return;
        setState({ status: "ready", expressions });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load expressions of interest.",
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [managementApi, reloadKey]);

  async function handleReview(eoiId: string, status: "UNDER_REVIEW" | "ACCEPTED" | "REJECTED") {
    setBusyId(eoiId);
    setActionError(null);
    try {
      // For "ACCEPTED" this is the one and only authoritative acceptance
      // operation (Phase F4.1) -- it atomically transitions the EOI and
      // creates the resulting Engagement server-side. There is no
      // separate "Create Engagement" action anywhere in this UI, which
      // is what makes a duplicate Engagement structurally impossible
      // from the frontend's side.
      await managementApi.reviewEoi(eoiId, status);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not update this expression of interest.");
    } finally {
      setBusyId(null);
    }
  }

  async function handleEngagementTransition(
    engagementId: string,
    status: Extract<EngagementStatus, "ACTIVE" | "COMPLETED" | "CANCELLED">,
  ) {
    setBusyId(engagementId);
    setActionError(null);
    try {
      await managementApi.updateEngagementStatus(engagementId, status);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not update this engagement.");
    } finally {
      setBusyId(null);
    }
  }

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading expressions of interest…
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

  const { expressions } = state;

  if (expressions.length === 0) {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground">
          No expressions of interest yet.
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
      {expressions.map((e) => {
        const busy = busyId === e.id;
        return (
          <Card key={e.id}>
            <CardHeader>
              <CardTitle className="text-sm">{e.opportunity_title ?? "Opportunity"}</CardTitle>
            </CardHeader>
            <CardContent className="flex flex-col gap-2">
              {e.message && <p className="text-sm text-muted-foreground">&ldquo;{e.message}&rdquo;</p>}
              <div className="flex items-center justify-between">
                <Badge variant="outline">{EOI_STATUS_LABELS[e.status]}</Badge>
                <div className="flex gap-1.5">
                  {e.status === "SUBMITTED" && (
                    <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleReview(e.id, "UNDER_REVIEW")}>
                      Move to review
                    </Button>
                  )}
                  {e.status === "UNDER_REVIEW" && (
                    <>
                      <Button size="sm" disabled={busy} onClick={() => void handleReview(e.id, "ACCEPTED")}>
                        <Check className="size-3.5" /> Accept &amp; Create Engagement
                      </Button>
                      <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleReview(e.id, "REJECTED")}>
                        <X className="size-3.5" /> Reject
                      </Button>
                    </>
                  )}
                </div>
              </div>
              {e.engagement && (
                <div className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2">
                  <p className="text-sm">
                    Engagement:{" "}
                    <span className="font-medium">{ENGAGEMENT_STATUS_LABELS[e.engagement.status]}</span>
                  </p>
                  <div className="flex gap-1.5">
                    {e.engagement.status === "PLANNED" && (
                      <>
                        <Button
                          size="sm"
                          disabled={busy}
                          onClick={() => void handleEngagementTransition(e.engagement!.id, "ACTIVE")}
                        >
                          Activate
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => void handleEngagementTransition(e.engagement!.id, "CANCELLED")}
                        >
                          Cancel
                        </Button>
                      </>
                    )}
                    {e.engagement.status === "ACTIVE" && (
                      <>
                        <Button
                          size="sm"
                          disabled={busy}
                          onClick={() => void handleEngagementTransition(e.engagement!.id, "COMPLETED")}
                        >
                          Complete
                        </Button>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={busy}
                          onClick={() => void handleEngagementTransition(e.engagement!.id, "CANCELLED")}
                        >
                          Cancel
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              )}
            </CardContent>
          </Card>
        );
      })}
    </div>
  );
}

function StatusBadge({ status }: { status: FacultyOpportunityPosting["status"] }) {
  if (status === "PUBLISHED") {
    return <Badge className="bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500">Published</Badge>;
  }
  if (status === "CLOSED") return <Badge variant="secondary">Closed</Badge>;
  return <Badge variant="outline">Draft</Badge>;
}
