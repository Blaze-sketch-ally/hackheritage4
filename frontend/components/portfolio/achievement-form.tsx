"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { createAchievement, updateAchievement } from "@/lib/student/portfolio";
import type { Achievement } from "@/types/portfolio";

/** Handles both create and edit -- one form, same convention as
 * ProjectForm/CertificationForm. Inline, not a modal. */
export function AchievementForm({
  achievement,
  onSaved,
  onCancel,
}: {
  achievement?: Achievement;
  onSaved: () => void;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(achievement?.title ?? "");
  const [description, setDescription] = useState(achievement?.description ?? "");
  const [achievementDate, setAchievementDate] = useState(achievement?.achievement_date ?? "");
  const [issuingOrganization, setIssuingOrganization] = useState(achievement?.issuing_organization ?? "");
  const [url, setUrl] = useState(achievement?.url ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = {
        title,
        description: description || null,
        achievement_date: achievementDate || null,
        issuing_organization: issuingOrganization || null,
        url: url || null,
      };
      if (achievement) {
        await updateAchievement(achievement.id, payload);
      } else {
        await createAchievement(payload);
      }
      onSaved();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this achievement.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{achievement ? "Edit Achievement" : "Add Achievement"}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="achievement-title">Title</Label>
            <Input id="achievement-title" value={title} onChange={(e) => setTitle(e.target.value)} required />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="achievement-description">Description</Label>
            <Textarea
              id="achievement-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
            />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="achievement-date">Date</Label>
              <Input
                id="achievement-date"
                type="date"
                value={achievementDate}
                onChange={(e) => setAchievementDate(e.target.value)}
              />
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="achievement-org">Issuing organization</Label>
              <Input
                id="achievement-org"
                value={issuingOrganization}
                onChange={(e) => setIssuingOrganization(e.target.value)}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="achievement-url">URL</Label>
            <Input
              id="achievement-url"
              type="url"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://example.com/..."
            />
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
