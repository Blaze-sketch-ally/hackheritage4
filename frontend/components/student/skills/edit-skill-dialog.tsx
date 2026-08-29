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
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import {
  PROFICIENCY_LEVEL_ITEMS,
  PROFICIENCY_LEVELS,
  type ProficiencyLevel,
  type StudentSkill,
} from "@/lib/student/skills";

function EditSkillForm({
  studentSkill,
  submitting,
  error,
  onCancel,
  onSave,
}: {
  studentSkill: StudentSkill;
  submitting: boolean;
  error: string | null;
  onCancel: () => void;
  onSave: (proficiency: ProficiencyLevel) => void;
}) {
  const [proficiency, setProficiency] = useState<ProficiencyLevel>(studentSkill.proficiency_level);

  return (
    <>
      <DialogHeader>
        <DialogTitle>Edit Proficiency</DialogTitle>
        <DialogDescription>{studentSkill.skill.name}</DialogDescription>
      </DialogHeader>

      <FormError message={error} />

      <div className="space-y-1.5">
        <Label htmlFor="edit-skill-proficiency">Proficiency</Label>
        <Select
          value={proficiency}
          onValueChange={(next) => setProficiency(next as ProficiencyLevel)}
          disabled={submitting}
          items={PROFICIENCY_LEVEL_ITEMS}
        >
          <SelectTrigger id="edit-skill-proficiency" className="w-full">
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

      <DialogFooter>
        <Button variant="outline" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button onClick={() => onSave(proficiency)} disabled={submitting}>
          {submitting ? "Saving..." : "Save"}
        </Button>
      </DialogFooter>
    </>
  );
}

export function EditSkillDialog({
  studentSkill,
  onOpenChange,
  submitting,
  error,
  onSave,
}: {
  studentSkill: StudentSkill | null;
  onOpenChange: (open: boolean) => void;
  submitting: boolean;
  error: string | null;
  onSave: (proficiency: ProficiencyLevel) => void;
}) {
  // Keeps the last skill on screen while the close animation plays, instead
  // of blanking the dialog the instant `studentSkill` goes null.
  const [displaySkill, setDisplaySkill] = useState(studentSkill);
  if (studentSkill && studentSkill !== displaySkill) {
    setDisplaySkill(studentSkill);
  }

  return (
    <Dialog open={!!studentSkill} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-sm">
        {displaySkill ? (
          <EditSkillForm
            key={displaySkill.id}
            studentSkill={displaySkill}
            submitting={submitting}
            error={error}
            onCancel={() => onOpenChange(false)}
            onSave={onSave}
          />
        ) : null}
      </DialogContent>
    </Dialog>
  );
}
