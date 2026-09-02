"use client";

import { useEffect, useMemo, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { FormError } from "@/components/auth/form-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { createClient } from "@/lib/supabase/client";
import { fetchActiveSkills, type CatalogSkill } from "@/lib/student/skills";
import { isValidUrl } from "@/lib/validations";
import type { ProjectInput, StudentProject } from "@/types/student-portfolio";

const EMPTY: ProjectInput = {
  title: "",
  description: "",
  project_url: "",
  repo_url: "",
  start_date: "",
  end_date: "",
  is_ongoing: false,
  skill_ids: [],
};

function toInput(project: StudentProject): ProjectInput {
  return {
    title: project.title,
    description: project.description ?? "",
    project_url: project.project_url ?? "",
    repo_url: project.repo_url ?? "",
    start_date: project.start_date ?? "",
    end_date: project.end_date ?? "",
    is_ongoing: project.is_ongoing,
    skill_ids: project.skills.map((s) => s.skill_id),
  };
}

/** Trims empties to null and drops "" dates -- the shape the API expects. */
export function normalizeProjectInput(form: ProjectInput): ProjectInput {
  return {
    title: form.title.trim(),
    description: form.description?.trim() || null,
    project_url: form.project_url?.trim() || null,
    repo_url: form.repo_url?.trim() || null,
    start_date: form.start_date || null,
    end_date: form.is_ongoing ? null : form.end_date || null,
    is_ongoing: !!form.is_ongoing,
    skill_ids: form.skill_ids ?? [],
  };
}

export function ProjectFormDialog({
  open,
  onOpenChange,
  project,
  submitting,
  error,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  project: StudentProject | null;
  submitting: boolean;
  error: string | null;
  onSubmit: (input: ProjectInput) => void;
}) {
  const [form, setForm] = useState<ProjectInput>(EMPTY);
  const [localError, setLocalError] = useState<string | null>(null);
  const [catalog, setCatalog] = useState<CatalogSkill[]>([]);
  const [skillSearch, setSkillSearch] = useState("");

  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setForm(project ? toInput(project) : EMPTY);
      setLocalError(null);
      setSkillSearch("");
    }
  }

  useEffect(() => {
    if (!open || catalog.length > 0) return;
    let cancelled = false;
    fetchActiveSkills(createClient())
      .then((skills) => {
        if (!cancelled) setCatalog(skills);
      })
      .catch(() => {
        /* skill picker just stays empty -- the project still saves */
      });
    return () => {
      cancelled = true;
    };
  }, [open, catalog.length]);

  const skillNameById = useMemo(
    () => new Map(catalog.map((s) => [s.id, s.name])),
    [catalog],
  );
  const selected = useMemo(() => form.skill_ids ?? [], [form.skill_ids]);
  const filteredCatalog = useMemo(() => {
    const q = skillSearch.trim().toLowerCase();
    return catalog
      .filter((s) => !selected.includes(s.id))
      .filter((s) => !q || s.name.toLowerCase().includes(q))
      .slice(0, 8);
  }, [catalog, selected, skillSearch]);

  function set<K extends keyof ProjectInput>(key: K, value: ProjectInput[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function toggleSkill(id: string, add: boolean) {
    setForm((f) => ({
      ...f,
      skill_ids: add
        ? [...(f.skill_ids ?? []), id]
        : (f.skill_ids ?? []).filter((s) => s !== id),
    }));
  }

  function handleSubmit() {
    setLocalError(null);
    if (!form.title.trim()) {
      setLocalError("Give your project a title.");
      return;
    }
    for (const [label, value] of [
      ["Project URL", form.project_url],
      ["Repository URL", form.repo_url],
    ] as const) {
      if (value && value.trim() && !isValidUrl(value)) {
        setLocalError(`${label} must be a valid http(s) URL.`);
        return;
      }
    }
    if (!form.is_ongoing && form.start_date && form.end_date && form.end_date < form.start_date) {
      setLocalError("End date can't be before the start date.");
      return;
    }
    onSubmit(normalizeProjectInput(form));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{project ? "Edit project" : "Add a project"}</DialogTitle>
          <DialogDescription>
            Record something you built. This is portfolio evidence only — it doesn&apos;t change
            your skills or verification.
          </DialogDescription>
        </DialogHeader>

        <FormError message={localError ?? error} />

        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          <div className="space-y-1.5">
            <Label htmlFor="project-title">Title *</Label>
            <Input
              id="project-title"
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
              placeholder="e.g. Skill Gap Analyzer"
              maxLength={200}
              disabled={submitting}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="project-description">Description</Label>
            <Textarea
              id="project-description"
              value={form.description ?? ""}
              onChange={(e) => set("description", e.target.value)}
              placeholder="What it does, your role, the stack..."
              rows={3}
              maxLength={5000}
              disabled={submitting}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="project-url">Project URL</Label>
              <Input
                id="project-url"
                value={form.project_url ?? ""}
                onChange={(e) => set("project_url", e.target.value)}
                placeholder="https://..."
                inputMode="url"
                disabled={submitting}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="project-repo">Repository URL</Label>
              <Input
                id="project-repo"
                value={form.repo_url ?? ""}
                onChange={(e) => set("repo_url", e.target.value)}
                placeholder="https://github.com/..."
                inputMode="url"
                disabled={submitting}
              />
            </div>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="project-start">Start date</Label>
              <Input
                id="project-start"
                type="date"
                value={form.start_date ?? ""}
                onChange={(e) => set("start_date", e.target.value)}
                disabled={submitting}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="project-end">End date</Label>
              <Input
                id="project-end"
                type="date"
                value={form.end_date ?? ""}
                onChange={(e) => set("end_date", e.target.value)}
                disabled={submitting || !!form.is_ongoing}
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={!!form.is_ongoing}
              onChange={(e) => set("is_ongoing", e.target.checked)}
              disabled={submitting}
              className="size-4"
            />
            This project is ongoing
          </label>

          <div className="space-y-1.5">
            <Label>Skills shown (optional)</Label>
            {selected.length > 0 && (
              <div className="flex flex-wrap gap-1">
                {selected.map((id) => (
                  <Badge key={id} variant="secondary" className="gap-1">
                    {skillNameById.get(id) ?? "Skill"}
                    <button
                      type="button"
                      onClick={() => toggleSkill(id, false)}
                      aria-label={`Remove ${skillNameById.get(id) ?? "skill"}`}
                      className="rounded hover:text-destructive"
                      disabled={submitting}
                    >
                      <X className="size-3" />
                    </button>
                  </Badge>
                ))}
              </div>
            )}
            <Input
              value={skillSearch}
              onChange={(e) => setSkillSearch(e.target.value)}
              placeholder="Search the skill catalog..."
              aria-label="Search skills to add to this project"
              disabled={submitting || catalog.length === 0}
            />
            {skillSearch.trim() && filteredCatalog.length > 0 && (
              <div className="rounded-lg border border-border/60">
                {filteredCatalog.map((s) => (
                  <button
                    key={s.id}
                    type="button"
                    onClick={() => {
                      toggleSkill(s.id, true);
                      setSkillSearch("");
                    }}
                    className="flex w-full px-3 py-1.5 text-left text-sm hover:bg-muted"
                    disabled={submitting}
                  >
                    {s.name}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Saving..." : project ? "Save changes" : "Add project"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
