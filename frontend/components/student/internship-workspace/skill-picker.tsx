"use client";

import { useMemo, useState } from "react";
import { AlertCircle, Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { WorkspaceProgramSkill } from "@/types/internship-workspace";

function sameSet(a: string[], b: string[]): boolean {
  if (a.length !== b.length) return false;
  const setB = new Set(b);
  return a.every((x) => setB.has(x));
}

/** Required skills are always in scope and read-only. Optional skills are
 * a toggle; "Save training skills" sends the full desired OPTIONAL set
 * (replace-set) via the parent's onSave. */
export function SkillPicker({
  skills,
  selectedSkillIds,
  onSave,
}: {
  skills: WorkspaceProgramSkill[];
  selectedSkillIds: string[];
  onSave: (skillIds: string[]) => Promise<void>;
}) {
  const required = useMemo(
    () => skills.filter((s) => s.requirement === "REQUIRED"),
    [skills],
  );
  const optional = useMemo(
    () => skills.filter((s) => s.requirement === "OPTIONAL"),
    [skills],
  );

  // `lastSaved` starts from the server's current selection and advances
  // only when a save succeeds -- so the component is self-contained and
  // does not depend on the parent re-passing `selectedSkillIds`.
  const [lastSaved, setLastSaved] = useState<string[]>(selectedSkillIds);
  const [draft, setDraft] = useState<string[]>(selectedSkillIds);
  const [state, setState] = useState<"idle" | "saving" | "saved">("idle");
  const [error, setError] = useState<string | null>(null);

  const dirty = !sameSet(draft, lastSaved);

  function toggle(skillId: string) {
    setState("idle");
    setError(null);
    setDraft((prev) =>
      prev.includes(skillId) ? prev.filter((x) => x !== skillId) : [...prev, skillId],
    );
  }

  async function save() {
    setState("saving");
    setError(null);
    try {
      await onSave(draft);
      setLastSaved(draft);
      setState("saved");
    } catch (err) {
      setState("idle");
      setError(err instanceof Error ? err.message : "Could not save your training skills.");
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Training skills</CardTitle>
        <p className="text-sm text-muted-foreground">
          Required skills are always part of your internship. Choose any optional
          skills you also want to focus on.
        </p>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        {required.length > 0 && (
          <div className="flex flex-col gap-1.5">
            <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
              Required
            </p>
            <div className="flex flex-wrap gap-2">
              {required.map((s) => (
                <span
                  key={s.skill_id}
                  className="inline-flex items-center gap-1.5 rounded-full bg-muted px-2.5 py-1 text-sm"
                >
                  <Check className="size-3.5 text-emerald-600" aria-hidden="true" />
                  {s.skill_name}
                </span>
              ))}
            </div>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
            Optional
          </p>
          {optional.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              This program has no optional skills.
            </p>
          ) : (
            <div className="flex flex-wrap gap-2">
              {optional.map((s) => {
                const on = draft.includes(s.skill_id);
                return (
                  <button
                    key={s.skill_id}
                    type="button"
                    aria-pressed={on}
                    onClick={() => toggle(s.skill_id)}
                    className={cn(
                      "inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1 text-sm transition-colors",
                      on
                        ? "border-indigo-600 bg-indigo-500/10 text-indigo-700 dark:text-indigo-300"
                        : "border-border text-foreground/70 hover:bg-muted",
                    )}
                  >
                    {on && <Check className="size-3.5" aria-hidden="true" />}
                    {s.skill_name}
                  </button>
                );
              })}
            </div>
          )}
        </div>

        {error && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="size-3.5" /> {error}
          </p>
        )}

        {optional.length > 0 && (
          <div className="flex items-center gap-3">
            <Button size="sm" onClick={save} disabled={!dirty || state === "saving"}>
              {state === "saving" && <Loader2 className="size-3.5 animate-spin" />}
              Save training skills
            </Button>
            {state === "saved" && !dirty && (
              <span className="flex items-center gap-1 text-sm text-emerald-600">
                <Check className="size-3.5" /> Saved
              </span>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
