"use client";

import { useMemo, useState } from "react";
import { Loader2, X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";
import type {
  AvailableSkill,
  ProgramSkill,
  SkillRequirement,
} from "@/types/internship-program";

type Draft = Record<string, SkillRequirement>;

function sameDraft(a: Draft, b: Draft): boolean {
  const ak = Object.keys(a);
  const bk = Object.keys(b);
  return ak.length === bk.length && ak.every((k) => a[k] === b[k]);
}

/** Program skills come ONLY from the internship's own recruitment skills
 * (internship_skills). Each selected skill is Required or Optional.
 * "Save skills" sends the full replace-set. */
export function ProgramSkillsEditor({
  skills,
  availableSkills,
  busy,
  onSave,
}: {
  skills: ProgramSkill[];
  availableSkills: AvailableSkill[];
  busy: boolean;
  onSave: (skills: { skill_id: string; requirement: SkillRequirement }[]) => Promise<boolean>;
}) {
  const saved: Draft = useMemo(
    () => Object.fromEntries(skills.map((s) => [s.skill_id, s.requirement])),
    [skills],
  );
  const nameOf = useMemo(
    () => Object.fromEntries(availableSkills.map((s) => [s.skill_id, s.skill_name])),
    [availableSkills],
  );

  const [draft, setDraft] = useState<Draft>(saved);
  const [pendingAdd, setPendingAdd] = useState<string>("");
  const [savingState, setSavingState] = useState<"idle" | "saving" | "saved">("idle");

  const dirty = !sameDraft(draft, saved);
  const notAdded = availableSkills.filter((s) => !(s.skill_id in draft));

  function setRequirement(id: string, requirement: SkillRequirement) {
    setSavingState("idle");
    setDraft((prev) => ({ ...prev, [id]: requirement }));
  }
  function remove(id: string) {
    setSavingState("idle");
    setDraft((prev) => {
      const next = { ...prev };
      delete next[id];
      return next;
    });
  }
  function add() {
    if (!pendingAdd) return;
    setRequirement(pendingAdd, "REQUIRED");
    setPendingAdd("");
  }

  async function save() {
    setSavingState("saving");
    const ok = await onSave(
      Object.entries(draft).map(([skill_id, requirement]) => ({ skill_id, requirement })),
    );
    // failure is shown in the parent's top-level error banner
    setSavingState(ok ? "saved" : "idle");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Skills</CardTitle>
        <p className="text-sm text-muted-foreground">
          Choose from this internship&apos;s required skills. Add a skill to the
          internship posting first if it isn&apos;t listed.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {availableSkills.length === 0 ? (
          <p className="text-sm text-muted-foreground">
            This internship has no skills yet. Add them on the internship posting.
          </p>
        ) : (
          <>
            <div className="flex flex-col gap-2">
              {Object.keys(draft).length === 0 ? (
                <p className="text-sm text-muted-foreground">No skills selected.</p>
              ) : (
                Object.entries(draft).map(([id, req]) => (
                  <div key={id} className="flex flex-wrap items-center gap-2">
                    <span className="text-sm font-medium">{nameOf[id] ?? id}</span>
                    <div className="flex overflow-hidden rounded-md border text-xs">
                      {(["REQUIRED", "OPTIONAL"] as SkillRequirement[]).map((r) => (
                        <button
                          key={r}
                          type="button"
                          aria-pressed={req === r}
                          disabled={busy || savingState === "saving"}
                          onClick={() => setRequirement(id, r)}
                          className={cn(
                            "px-2 py-1 transition-colors",
                            req === r
                              ? "bg-indigo-500/10 font-medium text-indigo-700 dark:text-indigo-300"
                              : "text-muted-foreground hover:bg-muted",
                          )}
                        >
                          {r === "REQUIRED" ? "Required" : "Optional"}
                        </button>
                      ))}
                    </div>
                    <Button
                      size="icon-xs"
                      variant="ghost"
                      aria-label={`Remove ${nameOf[id] ?? id}`}
                      disabled={busy || savingState === "saving"}
                      onClick={() => remove(id)}
                    >
                      <X />
                    </Button>
                  </div>
                ))
              )}
            </div>

            {notAdded.length > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <Select
                  value={pendingAdd}
                  onValueChange={(v) => setPendingAdd(v ?? "")}
                  disabled={busy || savingState === "saving"}
                >
                  <SelectTrigger className="w-56">
                    <SelectValue placeholder="Add a skill…" />
                  </SelectTrigger>
                  <SelectContent>
                    {notAdded.map((s) => (
                      <SelectItem key={s.skill_id} value={s.skill_id}>
                        {s.skill_name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
                <Button size="sm" variant="outline" onClick={add} disabled={!pendingAdd}>
                  Add
                </Button>
              </div>
            )}

            {skills.length > 0 && !dirty && savingState !== "saved" && (
              <div className="flex flex-wrap gap-1.5">
                {skills.map((s) => (
                  <Badge key={s.skill_id} variant={s.requirement === "REQUIRED" ? "secondary" : "outline"}>
                    {s.skill_name} · {s.requirement === "REQUIRED" ? "Required" : "Optional"}
                  </Badge>
                ))}
              </div>
            )}

            <div className="flex items-center gap-3">
              <Button
                size="sm"
                onClick={save}
                disabled={!dirty || busy || savingState === "saving"}
              >
                {savingState === "saving" && <Loader2 className="size-3.5 animate-spin" />}
                Save skills
              </Button>
              {savingState === "saved" && !dirty && (
                <span className="text-sm text-emerald-600">Saved</span>
              )}
            </div>
          </>
        )}
      </CardContent>
    </Card>
  );
}
