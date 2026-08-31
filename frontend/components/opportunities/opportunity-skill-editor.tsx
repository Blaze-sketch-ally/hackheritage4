"use client";

import { useEffect, useState } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { getRequirements, replaceRequirements } from "@/lib/industry/opportunities";
import { fetchActiveSkills, type CatalogSkill } from "@/lib/student/skills";
import { createClient } from "@/lib/supabase/client";
import type { OpportunityRequirement } from "@/types/opportunity";

interface DraftRequirement {
  skillId: string;
  requiredLevel: string;
  weight: string;
}

/** Add/remove required skills for one opportunity -- only ever called
 * while that opportunity is still DRAFT (the parent page hides this
 * editor otherwise; the backend independently enforces the same rule
 * via RLS + an explicit check, see app/api/opportunities.py). Reuses the
 * existing skills catalog fetch (lib/student/skills.ts) rather than
 * inventing a second one -- the catalog is readable by any authenticated
 * role. */
export function OpportunitySkillEditor({ opportunityId }: { opportunityId: string }) {
  const [catalog, setCatalog] = useState<CatalogSkill[]>([]);
  const [requirements, setRequirements] = useState<OpportunityRequirement[]>([]);
  const [draft, setDraft] = useState<DraftRequirement>({ skillId: "", requiredLevel: "70", weight: "1.0" });
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [skills, { requirements: reqs }] = await Promise.all([
          fetchActiveSkills(createClient()),
          getRequirements(opportunityId),
        ]);
        if (cancelled) return;
        setCatalog(skills);
        setRequirements(reqs);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err.message : "Could not load requirements.");
      } finally {
        if (!cancelled) setLoading(false);
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [opportunityId]);

  const availableSkills = catalog.filter((s) => !requirements.some((r) => r.skill_id === s.id));
  const skillItems = Object.fromEntries(availableSkills.map((s) => [s.id, s.name]));

  async function persist(next: OpportunityRequirement[]) {
    setSaving(true);
    setError(null);
    try {
      const { requirements: saved } = await replaceRequirements(
        opportunityId,
        next.map((r) => ({ skill_id: r.skill_id, required_level: r.required_level, weight: r.weight })),
      );
      setRequirements(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save requirements.");
    } finally {
      setSaving(false);
    }
  }

  function handleAdd() {
    if (!draft.skillId) return;
    const skill = catalog.find((s) => s.id === draft.skillId);
    if (!skill) return;
    const next: OpportunityRequirement[] = [
      ...requirements,
      { skill_id: skill.id, skill_name: skill.name, required_level: draft.requiredLevel, weight: draft.weight },
    ];
    setDraft({ skillId: "", requiredLevel: "70", weight: "1.0" });
    void persist(next);
  }

  function handleRemove(skillId: string) {
    void persist(requirements.filter((r) => r.skill_id !== skillId));
  }

  if (loading) {
    return <div className="h-32 animate-pulse rounded-lg bg-muted" aria-busy="true" aria-label="Loading requirements" />;
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Required Skills</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {error && <p className="text-sm text-destructive">{error}</p>}

        {requirements.length > 0 && (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Skill</TableHead>
                <TableHead className="text-right">Required Level</TableHead>
                <TableHead className="text-right">Weight</TableHead>
                <TableHead className="w-10" />
              </TableRow>
            </TableHeader>
            <TableBody>
              {requirements.map((r) => (
                <TableRow key={r.skill_id}>
                  <TableCell className="font-medium">{r.skill_name}</TableCell>
                  <TableCell className="text-right tabular-nums">{Number(r.required_level).toFixed(0)}</TableCell>
                  <TableCell className="text-right tabular-nums">{Number(r.weight).toFixed(2)}</TableCell>
                  <TableCell>
                    <Button
                      variant="ghost"
                      size="icon"
                      disabled={saving}
                      onClick={() => handleRemove(r.skill_id)}
                      aria-label={`Remove ${r.skill_name}`}
                    >
                      <Trash2 className="size-4" />
                    </Button>
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}

        {availableSkills.length > 0 && (
          <div className="flex flex-wrap items-end gap-2 rounded-lg border border-dashed p-3">
            <div className="min-w-40 flex-1 space-y-1">
              <label className="text-xs text-muted-foreground">Skill</label>
              <Select
                value={draft.skillId || undefined}
                onValueChange={(v) => setDraft((d) => ({ ...d, skillId: v ?? "" }))}
                items={skillItems}
              >
                <SelectTrigger className="w-full">
                  <SelectValue placeholder="Choose a skill" />
                </SelectTrigger>
                <SelectContent>
                  {availableSkills.map((s) => (
                    <SelectItem key={s.id} value={s.id}>
                      {s.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="w-28 space-y-1">
              <label className="text-xs text-muted-foreground">Required level</label>
              <Input
                type="number"
                min={0}
                max={100}
                value={draft.requiredLevel}
                onChange={(e) => setDraft((d) => ({ ...d, requiredLevel: e.target.value }))}
              />
            </div>
            <div className="w-24 space-y-1">
              <label className="text-xs text-muted-foreground">Weight</label>
              <Input
                type="number"
                min={0}
                step="0.25"
                value={draft.weight}
                onChange={(e) => setDraft((d) => ({ ...d, weight: e.target.value }))}
              />
            </div>
            <Button onClick={handleAdd} disabled={!draft.skillId || saving}>
              <Plus /> Add
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
