"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Plus, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ProjectCard } from "@/components/portfolio/project-card";
import { ProjectForm } from "@/components/portfolio/project-form";
import { ApiError } from "@/lib/api";
import { deleteProject, listMyProjects } from "@/lib/student/portfolio";
import type { Project } from "@/types/portfolio";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; projects: Project[] };

/** The student's own editable project list -- self-fetching, used by
 * both /student/portfolio (alongside CertificationList) and
 * /student/projects (alone), never a second implementation for either
 * route. */
export function ProjectList() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [formMode, setFormMode] = useState<"none" | "create" | string>("none");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { projects } = await listMyProjects();
        if (cancelled) return;
        setState({ status: "ready", projects });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your projects."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function refresh() {
    setFormMode("none");
    setReloadKey((k) => k + 1);
  }

  async function handleDelete(projectId: string) {
    if (!window.confirm("Delete this project? This cannot be undone.")) return;
    try {
      await deleteProject(projectId);
      setReloadKey((k) => k + 1);
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : "Could not delete this project.");
    }
  }

  if (state.status === "loading") {
    return <div className="h-40 animate-pulse rounded-lg bg-muted" aria-busy="true" aria-label="Loading projects" />;
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load your projects.</p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setState({ status: "loading" });
              setReloadKey((k) => k + 1);
            }}
          >
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { projects } = state;
  const editingProject = formMode !== "none" && formMode !== "create" ? projects.find((p) => p.id === formMode) : undefined;

  return (
    <div className="space-y-4">
      {formMode === "create" && <ProjectForm onSaved={refresh} onCancel={() => setFormMode("none")} />}
      {editingProject && (
        <ProjectForm project={editingProject} onSaved={refresh} onCancel={() => setFormMode("none")} />
      )}

      {formMode === "none" && (
        <>
          {projects.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center text-muted-foreground">
                <p>Add your first project to showcase your work.</p>
                <Button size="sm" onClick={() => setFormMode("create")}>
                  <Plus className="size-3.5" /> Add Project
                </Button>
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="flex justify-end">
                <Button size="sm" onClick={() => setFormMode("create")}>
                  <Plus className="size-3.5" /> Add Project
                </Button>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {projects.map((project) => (
                  <ProjectCard
                    key={project.id}
                    project={project}
                    onEdit={() => setFormMode(project.id)}
                    onDelete={() => handleDelete(project.id)}
                  />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
