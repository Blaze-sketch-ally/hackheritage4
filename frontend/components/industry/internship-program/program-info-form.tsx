"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { ProgramMeta, ProgramMetaInput } from "@/types/internship-program";

/** Program metadata -- only the columns that exist in
 * internship_programs (title, summary, estimated_weeks). Own Save button;
 * `onSave` returns a promise so the parent owns the network + bundle. */
export function ProgramInfoForm({
  program,
  busy,
  onSave,
}: {
  program: ProgramMeta;
  busy: boolean;
  onSave: (data: ProgramMetaInput) => Promise<boolean>;
}) {
  const [title, setTitle] = useState(program.title);
  const [summary, setSummary] = useState(program.summary ?? "");
  const [weeks, setWeeks] = useState(program.estimated_weeks?.toString() ?? "");
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  async function save() {
    setSaving(true);
    setSaved(false);
    const ok = await onSave({
      title: title.trim(),
      summary: summary.trim() ? summary.trim() : null,
      estimated_weeks: weeks.trim() ? Number(weeks) : null,
    });
    setSaving(false);
    setSaved(ok); // failure is shown in the parent's top-level error banner
  }

  const invalid = !title.trim() || (weeks.trim() !== "" && !/^\d{1,2}$/.test(weeks.trim()));

  return (
    <Card>
      <CardHeader>
        <CardTitle>Program information</CardTitle>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <div className="space-y-1.5">
          <Label htmlFor="program-title">Program name</Label>
          <Input
            id="program-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            disabled={saving || busy}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="program-summary">Description</Label>
          <Textarea
            id="program-summary"
            value={summary}
            onChange={(e) => setSummary(e.target.value)}
            rows={3}
            maxLength={4000}
            disabled={saving || busy}
            placeholder="What the intern will learn and build."
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="program-weeks">Estimated length (weeks)</Label>
          <Input
            id="program-weeks"
            value={weeks}
            onChange={(e) => setWeeks(e.target.value.replace(/[^\d]/g, "").slice(0, 2))}
            inputMode="numeric"
            className="w-28"
            disabled={saving || busy}
            placeholder="e.g. 6"
          />
        </div>

        <div className="flex items-center gap-3">
          <Button size="sm" onClick={save} disabled={saving || busy || invalid}>
            {saving && <Loader2 className="size-3.5 animate-spin" />}
            Save
          </Button>
          {saved && !saving && <span className="text-sm text-emerald-600">Saved</span>}
        </div>
      </CardContent>
    </Card>
  );
}
