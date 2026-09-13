"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ClipboardList, FileText, Layers, ListChecks, Plus, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import {
  createAssignment,
  createCriterion,
  createModule,
  createProgram,
  createResource,
  deleteCriterion,
  getAssignments,
  getCriteria,
  getModules,
  getProgramForOpportunity,
  getResources,
  listWorkspaces,
  publishAssignment,
  publishModule,
  publishProgram,
  publishResource,
  unpublishAssignment,
  unpublishModule,
  unpublishResource,
} from "@/lib/industry/participation";
import {
  PARTICIPATION_KIND_LABELS,
  RESOURCE_TYPES,
  type AssignmentResponse,
  type CriterionResponse,
  type ModuleResponse,
  type ParticipationKind,
  type ProgramResponse,
  type ResourceResponse,
  type ResourceType,
  type WorkspaceResponse,
} from "@/types/participation";

type ProgramState =
  | { status: "loading" }
  | { status: "none" }
  | { status: "error"; message: string }
  | { status: "ready"; program: ProgramResponse };

/** Shared Industry workspace-management surface for a Project/Training/
 * Workshop opportunity -- Overview, Modules, Resources, Assignments,
 * Evaluation Criteria, and Participants, all driven by the same
 * Participation Workspace API regardless of `kind`. */
export function WorkspaceManageView({ kind, opportunityId }: { kind: ParticipationKind; opportunityId: string }) {
  const [state, setState] = useState<ProgramState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [creating, setCreating] = useState(false);
  const [title, setTitle] = useState("");
  const [description, setDescription] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getProgramForOpportunity(kind, opportunityId)
      .then((program) => !cancelled && setState({ status: "ready", program }))
      .catch((err) => {
        if (cancelled) return;
        if (err instanceof ApiError && err.status === 404) {
          setState({ status: "none" });
        } else {
          setState({ status: "error", message: err instanceof ApiError ? err.message : "Could not load this workspace." });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [kind, opportunityId, reloadKey]);

  async function handleCreate() {
    setCreating(true);
    setFormError(null);
    try {
      const fk = { PROJECT: "project_id", TRAINING: "training_id", WORKSHOP: "workshop_id" } as const;
      await createProgram({ kind, [fk[kind]]: opportunityId, title, description: description || null } as never);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setFormError(err instanceof ApiError ? err.message : "Could not create the program. Please try again.");
    } finally {
      setCreating(false);
    }
  }

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
          Loading…
        </CardContent>
      </Card>
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
          <p className="text-sm text-muted-foreground">{state.message}</p>
        </CardContent>
      </Card>
    );
  }

  if (state.status === "none") {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Create a Participation Program</CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          <p className="text-sm text-muted-foreground">
            Set up modules, resources, and assignments so selected/accepted students have a real workspace to work
            in.
          </p>
          <FormError message={formError} />
          <div className="space-y-2">
            <Input placeholder="Program title" value={title} onChange={(e) => setTitle(e.target.value)} />
            <Textarea
              placeholder="Description (optional)"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={3}
            />
          </div>
          <Button onClick={handleCreate} disabled={creating || !title.trim()}>
            <Plus className="size-4" /> Create Program
          </Button>
        </CardContent>
      </Card>
    );
  }

  return <ProgramManager program={state.program} kind={kind} onReload={() => setReloadKey((k) => k + 1)} />;
}

function ProgramManager({
  program,
  kind,
  onReload,
}: {
  program: ProgramResponse;
  kind: ParticipationKind;
  onReload: () => void;
}) {
  const [tab, setTab] = useState("overview");
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  async function handlePublish() {
    setPending(true);
    setActionError(null);
    try {
      await publishProgram(program.id);
      setActionSuccess("Program published.");
      onReload();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not publish. Please try again.");
    } finally {
      setPending(false);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div>
          <h2 className="text-lg font-semibold">{program.title}</h2>
          <p className="text-xs text-muted-foreground">
            {PARTICIPATION_KIND_LABELS[kind]} program · <Badge variant="ghost">{program.status}</Badge>
          </p>
        </div>
        {program.status !== "PUBLISHED" && (
          <Button size="sm" onClick={handlePublish} disabled={pending}>
            Publish
          </Button>
        )}
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

      <Tabs value={tab} onValueChange={setTab}>
        <TabsList>
          <TabsTrigger value="overview">Overview</TabsTrigger>
          <TabsTrigger value="modules">Modules</TabsTrigger>
          <TabsTrigger value="resources">Resources</TabsTrigger>
          <TabsTrigger value="assignments">Assignments</TabsTrigger>
          <TabsTrigger value="criteria">Evaluation Criteria</TabsTrigger>
          <TabsTrigger value="participants">Participants</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="pt-4">
          <Card>
            <CardContent className="space-y-2 py-4">
              <p className="text-sm whitespace-pre-line">{program.description || "No description yet."}</p>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="modules" className="pt-4">
          <ModulesPanel programId={program.id} />
        </TabsContent>

        <TabsContent value="resources" className="pt-4">
          <ResourcesPanel programId={program.id} />
        </TabsContent>

        <TabsContent value="assignments" className="pt-4">
          <AssignmentsPanel programId={program.id} />
        </TabsContent>

        <TabsContent value="criteria" className="pt-4">
          <CriteriaPanel programId={program.id} />
        </TabsContent>

        <TabsContent value="participants" className="pt-4">
          <ParticipantsPanel kind={kind} />
        </TabsContent>
      </Tabs>
    </div>
  );
}

function ModulesPanel({ programId }: { programId: string }) {
  const [modules, setModules] = useState<ModuleResponse[] | null>(null);
  const [title, setTitle] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    getModules(programId).then((r) => setModules(r.modules));
  }, [programId, reloadKey]);

  async function add() {
    if (!title.trim()) return;
    await createModule(programId, { title });
    setTitle("");
    setReloadKey((k) => k + 1);
  }

  async function togglePublish(m: ModuleResponse) {
    if (m.is_published) await unpublishModule(programId, m.id);
    else await publishModule(programId, m.id);
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Input placeholder="New module title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Button onClick={add} disabled={!title.trim()}>
          <Plus className="size-4" /> Add
        </Button>
      </div>
      {modules === null ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : modules.length === 0 ? (
        <EmptyState icon={Layers} title="No modules yet" description="Add sections for milestones, curriculum units, or session parts." />
      ) : (
        <div className="space-y-2">
          {modules.map((m) => (
            <Card key={m.id}>
              <CardContent className="flex items-center justify-between gap-2 py-3">
                <p className="font-medium">{m.title}</p>
                <div className="flex items-center gap-2">
                  <Badge variant={m.is_published ? "default" : "ghost"}>{m.is_published ? "Published" : "Draft"}</Badge>
                  <Button size="sm" variant="outline" onClick={() => togglePublish(m)}>
                    {m.is_published ? "Unpublish" : "Publish"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function ResourcesPanel({ programId }: { programId: string }) {
  const [resources, setResources] = useState<ResourceResponse[] | null>(null);
  const [title, setTitle] = useState("");
  const [url, setUrl] = useState("");
  const [resourceType, setResourceType] = useState<ResourceType>("LINK");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    getResources(programId).then((r) => setResources(r.resources));
  }, [programId, reloadKey]);

  async function add() {
    if (!title.trim()) return;
    await createResource(programId, { title, resource_type: resourceType, resource_url: url || null });
    setTitle("");
    setUrl("");
    setReloadKey((k) => k + 1);
  }

  async function togglePublish(r: ResourceResponse) {
    if (r.is_published) await unpublishResource(programId, r.id);
    else await publishResource(programId, r.id);
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap gap-2">
        <Input placeholder="Resource title" value={title} onChange={(e) => setTitle(e.target.value)} className="max-w-xs" />
        <Select value={resourceType} onValueChange={(v) => setResourceType((v as ResourceType) ?? "LINK")}>
          <SelectTrigger className="w-32">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {RESOURCE_TYPES.map((t) => (
              <SelectItem key={t} value={t}>
                {t}
              </SelectItem>
            ))}
          </SelectContent>
        </Select>
        <Input placeholder="URL (optional)" value={url} onChange={(e) => setUrl(e.target.value)} className="max-w-xs" />
        <Button onClick={add} disabled={!title.trim()}>
          <Plus className="size-4" /> Add
        </Button>
      </div>
      {resources === null ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : resources.length === 0 ? (
        <EmptyState icon={FileText} title="No resources yet" description="Add videos, documents, or links for participants." />
      ) : (
        <div className="space-y-2">
          {resources.map((r) => (
            <Card key={r.id}>
              <CardContent className="flex items-center justify-between gap-2 py-3">
                <div className="min-w-0">
                  <p className="font-medium">{r.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {r.resource_type}
                    {r.resource_url ? ` · ${r.resource_url}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={r.is_published ? "default" : "ghost"}>{r.is_published ? "Published" : "Draft"}</Badge>
                  <Button size="sm" variant="outline" onClick={() => togglePublish(r)}>
                    {r.is_published ? "Unpublish" : "Publish"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function AssignmentsPanel({ programId }: { programId: string }) {
  const [assignments, setAssignments] = useState<AssignmentResponse[] | null>(null);
  const [title, setTitle] = useState("");
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    getAssignments(programId).then((r) => setAssignments(r.assignments));
  }, [programId, reloadKey]);

  async function add() {
    if (!title.trim()) return;
    await createAssignment(programId, { title, is_required: true });
    setTitle("");
    setReloadKey((k) => k + 1);
  }

  async function togglePublish(a: AssignmentResponse) {
    if (a.is_published) await unpublishAssignment(programId, a.id);
    else await publishAssignment(programId, a.id);
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="space-y-3">
      <div className="flex gap-2">
        <Input placeholder="New assignment title" value={title} onChange={(e) => setTitle(e.target.value)} />
        <Button onClick={add} disabled={!title.trim()}>
          <Plus className="size-4" /> Add
        </Button>
      </div>
      {assignments === null ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : assignments.length === 0 ? (
        <EmptyState icon={ClipboardList} title="No assignments yet" description="Add gradable tasks or deliverables." />
      ) : (
        <div className="space-y-2">
          {assignments.map((a) => (
            <Card key={a.id}>
              <CardContent className="flex items-center justify-between gap-2 py-3">
                <div className="min-w-0">
                  <p className="font-medium">{a.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {a.is_required ? "Required" : "Optional"}
                    {a.max_score ? ` · Max score ${a.max_score}` : ""}
                  </p>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant={a.is_published ? "default" : "ghost"}>{a.is_published ? "Published" : "Draft"}</Badge>
                  <Button size="sm" variant="outline" onClick={() => togglePublish(a)}>
                    {a.is_published ? "Unpublish" : "Publish"}
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}
    </div>
  );
}

function CriteriaPanel({ programId }: { programId: string }) {
  const [criteria, setCriteria] = useState<CriterionResponse[] | null>(null);
  const [name, setName] = useState("");
  const [maxScore, setMaxScore] = useState("10");
  const [weight, setWeight] = useState("25");
  const [reloadKey, setReloadKey] = useState(0);
  const [confirmDeleteId, setConfirmDeleteId] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    getCriteria(programId).then((r) => setCriteria(r.criteria));
  }, [programId, reloadKey]);

  async function add() {
    if (!name.trim()) return;
    await createCriterion(programId, { name, max_score: Number(maxScore), weight: Number(weight) });
    setName("");
    setReloadKey((k) => k + 1);
  }

  async function remove() {
    if (!confirmDeleteId) return;
    try {
      await deleteCriterion(programId, confirmDeleteId);
      setReloadKey((k) => k + 1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not remove this criterion.");
    } finally {
      setConfirmDeleteId(null);
    }
  }

  const weightTotal = (criteria ?? []).reduce((sum, c) => sum + c.weight, 0);

  return (
    <div className="space-y-3">
      <FormError message={error} />
      <div className="flex flex-wrap gap-2">
        <Input placeholder="Criterion name" value={name} onChange={(e) => setName(e.target.value)} className="max-w-xs" />
        <Input placeholder="Max score" type="number" value={maxScore} onChange={(e) => setMaxScore(e.target.value)} className="w-28" />
        <Input placeholder="Weight %" type="number" value={weight} onChange={(e) => setWeight(e.target.value)} className="w-28" />
        <Button onClick={add} disabled={!name.trim()}>
          <Plus className="size-4" /> Add
        </Button>
      </div>
      {criteria === null ? (
        <p className="text-sm text-muted-foreground">Loading…</p>
      ) : criteria.length === 0 ? (
        <EmptyState icon={ListChecks} title="No evaluation criteria yet" description="Add a rubric to structure the final evaluation. Optional for lightweight workshops." />
      ) : (
        <>
          <div className="grid gap-2 sm:grid-cols-2">
            {criteria.map((c) => (
              <Card key={c.id}>
                <CardContent className="flex items-center justify-between gap-2 py-3">
                  <div>
                    <p className="font-medium">{c.name}</p>
                    <p className="text-xs text-muted-foreground">
                      Max {c.max_score} · Weight {c.weight}%
                    </p>
                  </div>
                  <Button size="sm" variant="ghost" onClick={() => setConfirmDeleteId(c.id)}>
                    Remove
                  </Button>
                </CardContent>
              </Card>
            ))}
          </div>
          <p className={`text-xs ${weightTotal === 100 ? "text-muted-foreground" : "text-amber-600 dark:text-amber-400"}`}>
            Total weight: {weightTotal}% {weightTotal !== 100 ? "(should typically add up to 100%)" : ""}
          </p>
        </>
      )}
      <ConfirmationDialog
        open={confirmDeleteId !== null}
        onOpenChange={(open) => !open && setConfirmDeleteId(null)}
        title="Remove this criterion?"
        confirmLabel="Remove"
        destructive
        loading={false}
        onConfirm={remove}
      />
    </div>
  );
}

function ParticipantsPanel({ kind }: { kind: ParticipationKind }) {
  const [workspaces, setWorkspaces] = useState<WorkspaceResponse[] | null>(null);

  useEffect(() => {
    listWorkspaces({ kind }).then((r) => setWorkspaces(r.workspaces));
  }, [kind]);

  if (workspaces === null) return <p className="text-sm text-muted-foreground">Loading…</p>;
  if (workspaces.length === 0) {
    return <EmptyState icon={Users} title="No participants yet" description="Selected/accepted students will appear here once their workspace is provisioned." />;
  }

  return (
    <div className="grid gap-3 sm:grid-cols-2">
      {workspaces.map((w) => (
        <Card key={w.id}>
          <CardContent className="flex items-center justify-between gap-2 py-3">
            <div className="min-w-0">
              <p className="truncate font-medium">{w.student_name ?? `Applicant ${w.student_id.slice(0, 8)}`}</p>
              <p className="text-xs text-muted-foreground">
                {w.opportunity?.title}
                {w.progress ? ` · ${w.progress.percent}% complete` : ""}
              </p>
            </div>
            <div className="flex items-center gap-2">
              <Badge variant={w.workspace_status === "COMPLETED" ? "default" : "ghost"}>{w.workspace_status}</Badge>
              <Button size="sm" variant="outline" render={<Link href={`/industry/participation/workspaces/${w.id}`} />}>
                Open
              </Button>
            </div>
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
