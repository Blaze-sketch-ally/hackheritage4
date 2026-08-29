"use client";

import { useMemo, useState } from "react";
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
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { SearchBar } from "@/components/common/search-bar";
import { cn } from "@/lib/utils";
import {
  PROFICIENCY_LEVEL_ITEMS,
  PROFICIENCY_LEVELS,
  type CatalogSkill,
  type ProficiencyLevel,
  type SkillCategory,
} from "@/lib/student/skills";

export function AddSkillDialog({
  open,
  onOpenChange,
  catalogSkills,
  categories,
  existingSkillIds,
  submitting,
  error,
  onAdd,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  catalogSkills: CatalogSkill[];
  categories: SkillCategory[];
  existingSkillIds: Set<string>;
  submitting: boolean;
  error: string | null;
  onAdd: (skillId: string, proficiency: ProficiencyLevel) => void;
}) {
  const [search, setSearch] = useState("");
  const [selectedSkillId, setSelectedSkillId] = useState<string | null>(null);
  const [proficiency, setProficiency] = useState<ProficiencyLevel>("Beginner");

  // Resets the form on any transition to closed — whether the user closed
  // it (backdrop/Escape/Cancel) or the parent closed it after a successful
  // save — so reopening always starts back at search, not mid-flow.
  const [wasOpen, setWasOpen] = useState(open);
  if (open !== wasOpen) {
    setWasOpen(open);
    if (!open) {
      setSearch("");
      setSelectedSkillId(null);
      setProficiency("Beginner");
    }
  }

  const categoryNameById = useMemo(() => new Map(categories.map((c) => [c.id, c.name])), [categories]);

  const filteredSkills = useMemo(() => {
    const query = search.trim().toLowerCase();
    if (!query) return catalogSkills;
    return catalogSkills.filter((skill) => skill.name.toLowerCase().includes(query));
  }, [catalogSkills, search]);

  const selectedSkill = catalogSkills.find((skill) => skill.id === selectedSkillId) ?? null;

  function handleSave() {
    if (!selectedSkillId) return;
    onAdd(selectedSkillId, proficiency);
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>Add a Skill</DialogTitle>
          <DialogDescription>
            {selectedSkill
              ? "Choose your proficiency level."
              : "Search the skill catalog to add one to your profile."}
          </DialogDescription>
        </DialogHeader>

        <FormError message={error} />

        {!selectedSkill ? (
          <div className="space-y-3">
            <SearchBar
              value={search}
              onChange={setSearch}
              placeholder="Search skills..."
              aria-label="Search skills"
            />
            <div className="max-h-72 space-y-1 overflow-y-auto">
              {filteredSkills.length === 0 ? (
                <p className="py-6 text-center text-sm text-muted-foreground">No matching skills found.</p>
              ) : (
                filteredSkills.map((skill) => {
                  const alreadyAdded = existingSkillIds.has(skill.id);
                  return (
                    <button
                      key={skill.id}
                      type="button"
                      disabled={alreadyAdded}
                      onClick={() => setSelectedSkillId(skill.id)}
                      className={cn(
                        "flex w-full items-center justify-between rounded-lg px-3 py-2 text-left text-sm transition-colors",
                        alreadyAdded ? "cursor-not-allowed opacity-50" : "hover:bg-muted",
                      )}
                    >
                      <span>
                        <span className="font-medium">{skill.name}</span>
                        <span className="ml-2 text-xs text-muted-foreground">
                          {categoryNameById.get(skill.category_id) ?? ""}
                        </span>
                      </span>
                      {alreadyAdded ? <span className="text-xs text-muted-foreground">Already added</span> : null}
                    </button>
                  );
                })
              )}
            </div>
          </div>
        ) : (
          <div className="space-y-4">
            <div className="rounded-lg border border-border/60 p-3">
              <p className="text-sm font-medium">{selectedSkill.name}</p>
              <p className="text-xs text-muted-foreground">{categoryNameById.get(selectedSkill.category_id) ?? ""}</p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor="add-skill-proficiency">Proficiency</Label>
              <Select
                value={proficiency}
                onValueChange={(next) => setProficiency(next as ProficiencyLevel)}
                disabled={submitting}
                items={PROFICIENCY_LEVEL_ITEMS}
              >
                <SelectTrigger id="add-skill-proficiency" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {PROFICIENCY_LEVELS.map((level) => (
                    <SelectItem key={level} value={level}>
                      {level}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </div>
        )}

        <DialogFooter>
          {selectedSkill ? (
            <Button variant="outline" onClick={() => setSelectedSkillId(null)} disabled={submitting}>
              Back
            </Button>
          ) : (
            <Button variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
          )}
          <Button onClick={handleSave} disabled={!selectedSkillId || submitting}>
            {submitting ? "Adding..." : "Add Skill"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
