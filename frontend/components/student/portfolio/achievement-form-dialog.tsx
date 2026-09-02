"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FormError } from "@/components/auth/form-error";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { isValidUrl } from "@/lib/validations";
import type { AchievementInput, StudentAchievement } from "@/types/student-portfolio";

const EMPTY: AchievementInput = {
  title: "",
  description: "",
  achievement_date: "",
  issuing_organization: "",
  url: "",
};

function toInput(a: StudentAchievement): AchievementInput {
  return {
    title: a.title,
    description: a.description ?? "",
    achievement_date: a.achievement_date ?? "",
    issuing_organization: a.issuing_organization ?? "",
    url: a.url ?? "",
  };
}

export function normalizeAchievementInput(form: AchievementInput): AchievementInput {
  return {
    title: form.title.trim(),
    description: form.description?.trim() || null,
    achievement_date: form.achievement_date || null,
    issuing_organization: form.issuing_organization?.trim() || null,
    url: form.url?.trim() || null,
  };
}

export function AchievementFormDialog({
  open,
  onOpenChange,
  achievement,
  submitting,
  error,
  onSubmit,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  achievement: StudentAchievement | null;
  submitting: boolean;
  error: string | null;
  onSubmit: (input: AchievementInput) => void;
}) {
  const [form, setForm] = useState<AchievementInput>(EMPTY);
  const [localError, setLocalError] = useState<string | null>(null);

  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (open) {
      setForm(achievement ? toInput(achievement) : EMPTY);
      setLocalError(null);
    }
  }

  function set<K extends keyof AchievementInput>(key: K, value: AchievementInput[K]) {
    setForm((f) => ({ ...f, [key]: value }));
  }

  function handleSubmit() {
    setLocalError(null);
    if (!form.title.trim()) {
      setLocalError("Give your achievement a title.");
      return;
    }
    if (form.url && form.url.trim() && !isValidUrl(form.url)) {
      setLocalError("URL must be a valid http(s) URL.");
      return;
    }
    onSubmit(normalizeAchievementInput(form));
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-lg">
        <DialogHeader>
          <DialogTitle>{achievement ? "Edit achievement" : "Add an achievement"}</DialogTitle>
          <DialogDescription>
            An award, recognition, or milestone. Portfolio evidence only.
          </DialogDescription>
        </DialogHeader>

        <FormError message={localError ?? error} />

        <div className="max-h-[60vh] space-y-4 overflow-y-auto pr-1">
          <div className="space-y-1.5">
            <Label htmlFor="ach-title">Title *</Label>
            <Input
              id="ach-title"
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
              placeholder="e.g. 1st place, HackHeritage 4"
              maxLength={200}
              disabled={submitting}
            />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ach-description">Description</Label>
            <Textarea
              id="ach-description"
              value={form.description ?? ""}
              onChange={(e) => set("description", e.target.value)}
              rows={3}
              maxLength={5000}
              disabled={submitting}
            />
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="ach-date">Date</Label>
              <Input
                id="ach-date"
                type="date"
                value={form.achievement_date ?? ""}
                onChange={(e) => set("achievement_date", e.target.value)}
                disabled={submitting}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="ach-org">Issued by</Label>
              <Input
                id="ach-org"
                value={form.issuing_organization ?? ""}
                onChange={(e) => set("issuing_organization", e.target.value)}
                maxLength={200}
                disabled={submitting}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="ach-url">URL</Label>
            <Input
              id="ach-url"
              value={form.url ?? ""}
              onChange={(e) => set("url", e.target.value)}
              placeholder="https://..."
              inputMode="url"
              disabled={submitting}
            />
          </div>
        </div>

        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={submitting}>
            {submitting ? "Saving..." : achievement ? "Save changes" : "Add achievement"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
