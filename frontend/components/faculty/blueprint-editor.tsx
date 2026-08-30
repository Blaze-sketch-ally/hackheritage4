"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardFooter, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { ApiError } from "@/lib/api";
import { getBlueprint, listAssessmentsForFaculty, replaceBlueprint } from "@/lib/faculty/question-bank";
import type { Assessment, Difficulty } from "@/types/assessment";

const DIFFICULTIES: Difficulty[] = ["Beginner", "Intermediate", "Advanced", "Expert"];

/** Defines how many APPROVED questions of each difficulty a student's
 * attempt should randomly draw for one assessment (Phase 1K). Saving
 * REPLACES the assessment's entire blueprint -- a difficulty left blank
 * or zero is simply not included in the saved blueprint at all. This is
 * the one screen that makes create_assessment_attempt() able to succeed
 * for an assessment; an assessment with no blueprint rejects every
 * attempt with 409 until one is saved here. */
export function BlueprintEditor() {
  const [assessments, setAssessments] = useState<Assessment[]>([]);
  const [assessmentId, setAssessmentId] = useState("");
  const [counts, setCounts] = useState<Record<Difficulty, string>>({
    Beginner: "",
    Intermediate: "",
    Advanced: "",
    Expert: "",
  });

  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { assessments: rows } = await listAssessmentsForFaculty();
        if (cancelled) return;
        setAssessments(rows);
        if (rows.length > 0) setAssessmentId(rows[0].id);
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof ApiError ? err.message : "Could not load assessments.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!assessmentId) return;
    let cancelled = false;
    async function loadBlueprint() {
      try {
        const blueprint = await getBlueprint(assessmentId);
        if (cancelled) return;
        const next: Record<Difficulty, string> = { Beginner: "", Intermediate: "", Advanced: "", Expert: "" };
        for (const rule of blueprint.rules) next[rule.difficulty] = String(rule.question_count);
        setCounts(next);
      } catch (err) {
        if (!cancelled) setLoadError(err instanceof ApiError ? err.message : "Could not load the blueprint.");
      }
    }
    void loadBlueprint();
    return () => {
      cancelled = true;
    };
  }, [assessmentId]);

  async function handleSave() {
    setSaving(true);
    setSaveError(null);
    setSaved(false);
    const rules = DIFFICULTIES.filter((d) => Number(counts[d]) > 0).map((d) => ({
      difficulty: d,
      question_count: Number(counts[d]),
    }));
    try {
      await replaceBlueprint(assessmentId, rules);
      setSaved(true);
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Could not save the blueprint.");
    } finally {
      setSaving(false);
    }
  }

  if (loading) {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading…
        </CardContent>
      </Card>
    );
  }

  const total = DIFFICULTIES.reduce((sum, d) => sum + (Number(counts[d]) || 0), 0);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-lg">Assessment blueprint</CardTitle>
        <CardDescription>
          How many approved questions of each difficulty a student&apos;s attempt should randomly draw.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {loadError && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="size-3.5 shrink-0" /> {loadError}
          </p>
        )}

        <div className="space-y-1.5">
          <Label htmlFor="bp-assessment">Assessment</Label>
          <Select
            value={assessmentId}
            onValueChange={(next) => {
              setAssessmentId(next ?? "");
              setSaved(false);
            }}
            items={Object.fromEntries(assessments.map((a) => [a.id, a.title]))}
          >
            <SelectTrigger id="bp-assessment" className="w-full">
              <SelectValue placeholder="Choose an assessment" />
            </SelectTrigger>
            <SelectContent>
              {assessments.map((a) => (
                <SelectItem key={a.id} value={a.id}>
                  {a.title}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {DIFFICULTIES.map((d) => (
            <div key={d} className="space-y-1.5">
              <Label htmlFor={`bp-${d}`}>{d}</Label>
              <Input
                id={`bp-${d}`}
                type="number"
                min="0"
                step="1"
                value={counts[d]}
                onChange={(e) => setCounts((prev) => ({ ...prev, [d]: e.target.value }))}
                placeholder="0"
              />
            </div>
          ))}
        </div>

        <p className="text-sm text-muted-foreground">Total: {total} question{total === 1 ? "" : "s"} per attempt.</p>
      </CardContent>
      <CardFooter className="flex-col items-stretch gap-2">
        {saveError && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="size-3.5 shrink-0" /> {saveError}
          </p>
        )}
        {saved && (
          <p className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
            <Check className="size-3.5" /> Blueprint saved.
          </p>
        )}
        <Button onClick={handleSave} disabled={saving || !assessmentId || total === 0}>
          {saving && <Loader2 className="size-3.5 animate-spin" />} Save blueprint
        </Button>
      </CardFooter>
    </Card>
  );
}
