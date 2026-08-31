"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { createProject, updateProject } from "@/lib/student/portfolio";
import type { Project } from "@/types/portfolio";

/** Handles both create and edit -- one form, not two near-identical
 * copies, matching the same convention as OpportunityForm (Phase 1M).
 * Inline (not a modal) -- this codebase has no established modal-driven
 * CRUD pattern yet, and base-ui's Dialog carries the same jsdom
 * pointer-interaction risk already documented for Select, so an inline
 * card avoids introducing that risk for a form this simple. */
export function ProjectForm({
  project,
  onSaved,
  onCancel,
}: {
  project?: Project;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(project?.title ?? "");
  const [description, setDescription] = useState(project?.description ?? "");
  const [technologies, setTechnologies] = useState((project?.technologies ?? []).join(", "));
  const [projectUrl, setProjectUrl] = useState(project?.project_url ?? "");
  const [githubUrl, setGithubUrl] = useState(project?.github_url ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    const parsedTechnologies = technologies
      .split(",")
      .map((t) => t.trim())
      .filter(Boolean);
    try {
      if (project) {
        await updateProject(project.id, {
          title,
          description,
          technologies: parsedTechnologies,
          project_url: projectUrl || null,
          github_url: githubUrl || null,
        });
      } else {
        await createProject({
          title,
          description,
          technologies: parsedTechnologies,
          project_url: projectUrl || null,
          github_url: githubUrl || null,
        });
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this project.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{project ? "Edit Project" : "Add Project"}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="proj-title">Project title</Label>
            <Input id="proj-title" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="proj-description">Description</Label>
            <Textarea
              id="proj-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              required
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="proj-tech">Technologies</Label>
            <Input
              id="proj-tech"
              value={technologies}
              onChange={(e) => setTechnologies(e.target.value)}
              placeholder="React, FastAPI, PostgreSQL"
            />
            <p className="text-xs text-muted-foreground">Comma-separated.</p>
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="proj-github">GitHub URL</Label>
              <Input
                id="proj-github"
                type="url"
                value={githubUrl}
                onChange={(e) => setGithubUrl(e.target.value)}
                placeholder="https://github.com/you/project"
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="proj-live">Live URL</Label>
              <Input
                id="proj-live"
                type="url"
                value={projectUrl}
                onChange={(e) => setProjectUrl(e.target.value)}
                placeholder="https://your-project.example.com"
              />
            </div>
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          <div className="flex gap-2">
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : "Save"}
            </Button>
            <Button type="button" variant="outline" onClick={onCancel} disabled={saving}>
              Cancel
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
