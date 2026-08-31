"use client";

import { useMemo, useState } from "react";
import { Plus, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { SearchBar } from "@/components/common/search-bar";
import { cn } from "@/lib/utils";
import type { CatalogSkill } from "@/lib/industry/skills";
import {
  REQUIRED_LEVELS,
  SKILL_IMPORTANCES,
  SKILL_IMPORTANCE_LABELS,
  type RequiredLevel,
  type SkillImportance,
  type SkillRequirementInput,
} from "@/types/skill-requirement";

/** Pick required skills for an opportunity (internship or job) from the
 * shared catalog. New skills can never be invented here — only catalog
 * rows are selectable. The catalog may be empty; that renders as
 * "No matching skills in the catalog." rather than crashing. */
export function SkillRequirementsPicker({
  catalog,
  value,
  onChange,
  disabled,
}: {
  catalog: CatalogSkill[];
  value: SkillRequirementInput[];
  onChange: (next: SkillRequirementInput[]) => void;
  disabled?: boolean;
}) {
  const [search, setSearch] = useState("");

  const selectedIds = useMemo(() => new Set(value.map((s) => s.skill_id)), [value]);
  const nameById = useMemo(() => new Map(catalog.map((s) => [s.id, s.name])), [catalog]);

  const matches = useMemo(() => {
    const query = search.trim().toLowerCase();
    return catalog
      .filter((s) => !selectedIds.has(s.id))
      .filter((s) => !query || s.name.toLowerCase().includes(query))
      .slice(0, 8);
  }, [catalog, search, selectedIds]);

  function add(skill: CatalogSkill) {
    onChange([
      ...value,
      { skill_id: skill.id, required_level: "Intermediate", importance: "IMPORTANT" },
    ]);
    setSearch("");
  }

  function remove(skillId: string) {
    onChange(value.filter((s) => s.skill_id !== skillId));
  }

  function patch(skillId: string, partial: Partial<SkillRequirementInput>) {
    onChange(value.map((s) => (s.skill_id === skillId ? { ...s, ...partial } : s)));
  }

  return (
    <div className="space-y-3">
      <div className="space-y-1.5">
        <Label>Add a required skill</Label>
        <SearchBar
          value={search}
          onChange={setSearch}
          placeholder="Search the skill catalog..."
          aria-label="Search skills"
        />
        {search.trim() ? (
          <div className="max-h-56 space-y-1 overflow-y-auto rounded-lg border p-1">
            {matches.length === 0 ? (
              <p className="px-2 py-3 text-center text-sm text-muted-foreground">
                No matching skills in the catalog.
              </p>
            ) : (
              matches.map((skill) => (
                <button
                  key={skill.id}
                  type="button"
                  disabled={disabled}
                  onClick={() => add(skill)}
                  className={cn(
                    "flex w-full items-center justify-between rounded-md px-2 py-1.5 text-left text-sm",
                    "hover:bg-muted disabled:pointer-events-none disabled:opacity-50",
                  )}
                >
                  <span>
                    <span className="font-medium">{skill.name}</span>
                    {skill.category_name ? (
                      <span className="ml-2 text-xs text-muted-foreground">{skill.category_name}</span>
                    ) : null}
                  </span>
                  <Plus className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                </button>
              ))
            )}
          </div>
        ) : null}
      </div>

      {value.length === 0 ? (
        <p className="text-sm text-muted-foreground/70">No skills added yet.</p>
      ) : (
        <ul className="space-y-2">
          {value.map((skill) => (
            <li
              key={skill.skill_id}
              className="flex flex-col gap-2 rounded-lg border p-2.5 sm:flex-row sm:items-center sm:justify-between"
            >
              <span className="text-sm font-medium">
                {nameById.get(skill.skill_id) ?? "Unknown skill"}
              </span>
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={skill.required_level}
                  onValueChange={(next) => patch(skill.skill_id, { required_level: next as RequiredLevel })}
                  disabled={disabled}
                >
                  <SelectTrigger className="h-7 w-36" aria-label={`Required level for ${nameById.get(skill.skill_id) ?? "skill"}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {REQUIRED_LEVELS.map((level) => (
                      <SelectItem key={level} value={level}>
                        {level}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Select
                  value={skill.importance}
                  onValueChange={(next) => patch(skill.skill_id, { importance: next as SkillImportance })}
                  disabled={disabled}
                >
                  <SelectTrigger className="h-7 w-32" aria-label={`Importance for ${nameById.get(skill.skill_id) ?? "skill"}`}>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {SKILL_IMPORTANCES.map((imp) => (
                      <SelectItem key={imp} value={imp}>
                        {SKILL_IMPORTANCE_LABELS[imp]}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button
                  type="button"
                  variant="ghost"
                  size="icon-sm"
                  onClick={() => remove(skill.skill_id)}
                  disabled={disabled}
                  aria-label={`Remove ${nameById.get(skill.skill_id) ?? "skill"}`}
                >
                  <X className="size-4" />
                </Button>
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
