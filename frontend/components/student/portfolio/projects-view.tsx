"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowUpRight, FolderKanban, Code2, Pencil, Plus, Trash2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { createProject, deleteProject, listProjects, updateProject } from "@/lib/student/portfolio";
import { ProjectFormDialog } from "@/components/student/portfolio/project-form-dialog";
import { formatDateRange, type ProjectInput, type StudentProject } from "@/types/student-portfolio";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; projects: StudentProject[] };

function errText(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

export function ProjectsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<StudentProject | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [deleting, setDeleting] = useState<StudentProject | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);

  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listProjects()
      .then(({ projects }) => {
        if (!cancelled) setState({ status: "ready", projects });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({ status: "error", message: errText(err, "Could not load your projects.") });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function openAdd() {
    setEditing(null);
    setFormError(null);
    setFormOpen(true);
  }

  function openEdit(project: StudentProject) {
    setEditing(project);
    setFormError(null);
    setFormOpen(true);
  }

  async function handleSubmit(input: ProjectInput) {
    setSubmitting(true);
    setFormError(null);
    setSuccess(null);
    try {
      if (editing) {
        const updated = await updateProject(editing.id, input);
        setState((s) =>
          s.status === "ready"
            ? { ...s, projects: s.projects.map((p) => (p.id === updated.id ? updated : p)) }
            : s,
        );
        setSuccess(`Updated "${updated.title}".`);
      } else {
        const created = await createProject(input);
        setState((s) =>
          s.status === "ready" ? { ...s, projects: [created, ...s.projects] } : s,
        );
        setSuccess(`Added "${created.title}".`);
      }
      setFormOpen(false);
    } catch (err) {
      setFormError(errText(err, "Could not save your project. Please try again."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await deleteProject(deleting.id);
      setState((s) =>
        s.status === "ready"
          ? { ...s, projects: s.projects.filter((p) => p.id !== deleting.id) }
          : s,
      );
      setSuccess(`Deleted "${deleting.title}".`);
      setDeleting(null);
    } catch (err) {
      setSuccess(null);
      setState((s) =>
        s.status === "ready" ? s : { status: "error", message: errText(err, "Could not delete.") },
      );
      setDeleting(null);
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Projects</h1>
          <p className="text-sm text-muted-foreground">
            Things you&apos;ve built. Shown on your portfolio — never used to verify a skill.
          </p>
        </div>
        {state.status === "ready" && state.projects.length > 0 && (
          <Button onClick={openAdd}>
            <Plus className="size-4" /> Add project
          </Button>
        )}
      </div>

      <FormSuccess message={success} />

      {state.status === "loading" && <ListSkeleton />}

      {state.status === "error" && (
        <ErrorState
          message={state.message}
          onRetry={() => {
            setState({ status: "loading" });
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {state.status === "ready" && state.projects.length === 0 && (
        <EmptyState
          icon={FolderKanban}
          title="No projects yet"
          description="Add a project to start building your portfolio."
          actionLabel="+ Add your first project"
          onAction={openAdd}
        />
      )}

      {state.status === "ready" && state.projects.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {state.projects.map((project) => {
            const range = formatDateRange(project.start_date, project.end_date, project.is_ongoing);
            return (
              <Card key={project.id} className="flex flex-col">
                <CardHeader>
                  <CardTitle className="text-base">
                    <Link
                      href={`/student/projects/${project.id}`}
                      className="hover:underline"
                    >
                      {project.title}
                    </Link>
                  </CardTitle>
                  {range && <p className="text-xs text-muted-foreground">{range}</p>}
                </CardHeader>
                <CardContent className="flex-1 space-y-2 text-sm text-muted-foreground">
                  {project.description && <p className="line-clamp-3">{project.description}</p>}
                  {project.skills.length > 0 && (
                    <div className="flex flex-wrap gap-1">
                      {project.skills.map((s) => (
                        <Badge key={s.skill_id} variant="outline" className="font-normal">
                          {s.skill_name}
                        </Badge>
                      ))}
                    </div>
                  )}
                  <div className="flex flex-wrap gap-3 text-xs">
                    {project.project_url && (
                      <a
                        href={project.project_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-foreground hover:underline"
                      >
                        <ArrowUpRight className="size-3" /> Live
                      </a>
                    )}
                    {project.repo_url && (
                      <a
                        href={project.repo_url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="flex items-center gap-1 text-foreground hover:underline"
                      >
                        <Code2 className="size-3" /> Code
                      </a>
                    )}
                  </div>
                </CardContent>
                <CardFooter className="gap-2">
                  <Button variant="outline" size="sm" onClick={() => openEdit(project)}>
                    <Pencil className="size-3.5" /> Edit
                  </Button>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-destructive hover:text-destructive"
                    onClick={() => setDeleting(project)}
                  >
                    <Trash2 className="size-3.5" /> Delete
                  </Button>
                </CardFooter>
              </Card>
            );
          })}
        </div>
      )}

      <ProjectFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        project={editing}
        submitting={submitting}
        error={formError}
        onSubmit={handleSubmit}
      />

      <ConfirmationDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete "${deleting?.title ?? "this project"}"?`}
        description="This can't be undone."
        confirmLabel="Delete project"
        destructive
        loading={deleteBusy}
        onConfirm={handleDelete}
      />
    </div>
  );
}

function ListSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2" aria-label="Loading projects" aria-busy="true">
      {[0, 1].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2 py-5">
            <div className="h-4 w-2/3 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-1/2 rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
