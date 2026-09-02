"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ArrowUpRight, Code2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { ErrorState } from "@/components/common/error-state";
import { ApiError } from "@/lib/api";
import { deleteProject, getProject, updateProject } from "@/lib/student/portfolio";
import { ProjectFormDialog } from "@/components/student/portfolio/project-form-dialog";
import { formatDateRange, type ProjectInput, type StudentProject } from "@/types/student-portfolio";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string; notFound: boolean }
  | { status: "ready"; project: StudentProject };

export function ProjectDetailView({ projectId }: { projectId: string }) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [editOpen, setEditOpen] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getProject(projectId)
      .then((project) => {
        if (!cancelled) setState({ status: "ready", project });
      })
      .catch((err) => {
        if (cancelled) return;
        const notFound = err instanceof ApiError && err.status === 404;
        setState({
          status: "error",
          notFound,
          message: notFound
            ? "This project is not available."
            : err instanceof ApiError
              ? err.message
              : "Could not load this project.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, reloadKey]);

  async function handleUpdate(input: ProjectInput) {
    setSubmitting(true);
    setFormError(null);
    try {
      const updated = await updateProject(projectId, input);
      setState({ status: "ready", project: updated });
      setEditOpen(false);
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "Could not save your project. Please try again.",
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    setDeleteBusy(true);
    try {
      await deleteProject(projectId);
      router.push("/student/projects");
    } catch {
      setDeleteBusy(false);
      setConfirmDelete(false);
    }
  }

  if (state.status === "loading") {
    return (
      <Card className="animate-pulse">
        <CardContent className="space-y-3 py-6">
          <div className="h-5 w-1/2 rounded bg-muted" />
          <div className="h-3 w-full rounded bg-muted" />
          <div className="h-3 w-2/3 rounded bg-muted" />
        </CardContent>
      </Card>
    );
  }

  if (state.status === "error") {
    return (
      <ErrorState
        message={state.message}
        onRetry={
          state.notFound
            ? undefined
            : () => {
                setState({ status: "loading" });
                setReloadKey((k) => k + 1);
              }
        }
      />
    );
  }

  const { project } = state;
  const range = formatDateRange(project.start_date, project.end_date, project.is_ongoing);

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <CardTitle className="text-xl">{project.title}</CardTitle>
              {range && <p className="mt-1 text-sm text-muted-foreground">{range}</p>}
            </div>
            <div className="flex gap-2">
              <Button variant="outline" size="sm" onClick={() => setEditOpen(true)}>
                Edit
              </Button>
              <Button
                variant="ghost"
                size="sm"
                className="text-destructive hover:text-destructive"
                onClick={() => setConfirmDelete(true)}
              >
                Delete
              </Button>
            </div>
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          {project.description && (
            <p className="text-sm whitespace-pre-wrap text-muted-foreground">
              {project.description}
            </p>
          )}

          {project.skills.length > 0 && (
            <div>
              <h3 className="text-sm font-medium">Skills shown</h3>
              <div className="mt-1.5 flex flex-wrap gap-1.5">
                {project.skills.map((s) => (
                  <Badge key={s.skill_id} variant="outline">
                    {s.skill_name}
                    {s.category_name ? ` · ${s.category_name}` : ""}
                  </Badge>
                ))}
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Listed as portfolio evidence — this does not change your skills or verification.
              </p>
            </div>
          )}

          <div className="flex flex-wrap gap-2">
            {project.project_url && (
              <Button
                variant="outline"
                size="sm"
                render={
                  <a href={project.project_url} target="_blank" rel="noopener noreferrer">
                    <ArrowUpRight className="size-3.5" /> Live project
                  </a>
                }
                nativeButton={false}
              />
            )}
            {project.repo_url && (
              <Button
                variant="outline"
                size="sm"
                render={
                  <a href={project.repo_url} target="_blank" rel="noopener noreferrer">
                    <Code2 className="size-3.5" /> Repository
                  </a>
                }
                nativeButton={false}
              />
            )}
          </div>
        </CardContent>
      </Card>

      <ProjectFormDialog
        open={editOpen}
        onOpenChange={setEditOpen}
        project={project}
        submitting={submitting}
        error={formError}
        onSubmit={handleUpdate}
      />

      <ConfirmationDialog
        open={confirmDelete}
        onOpenChange={setConfirmDelete}
        title={`Delete "${project.title}"?`}
        description="This can't be undone."
        confirmLabel="Delete project"
        destructive
        loading={deleteBusy}
        onConfirm={handleDelete}
      />
    </div>
  );
}
