"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  ASSIGNMENT_TYPES,
  ASSIGNMENT_TYPE_LABEL,
  SUBMISSION_KINDS,
  SUBMISSION_KIND_LABEL,
  type AssignmentInput,
  type AssignmentType,
  type ProgramAssignment,
  type ProgramSkill,
  type SubmissionKind,
} from "@/types/internship-program";

const SELECT_CLASS =
  "h-8 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:cursor-not-allowed disabled:opacity-50 dark:bg-input/30";

const REPO_KINDS: SubmissionKind[] = ["REPO", "MIXED"];

/** Add or edit an assignment (ASSIGNMENT / QUIZ / PROJECT -- one
 * normalized program_assignments row, no quiz engine). Mirrors the
 * program_assignments_repo_kind_consistent CHECK: "requires a repo" forces
 * a REPO/MIXED submission kind. There is no delete -- the parent hides an
 * assignment via is_published. */
export function AssignmentForm({
  assignment,
  programSkills,
  busy,
  onSubmit,
  onCancel,
}: {
  assignment?: ProgramAssignment;
  programSkills: ProgramSkill[];
  busy: boolean;
  onSubmit: (data: AssignmentInput & { title: string }) => Promise<void>;
  onCancel: () => void;
}) {
  const [title, setTitle] = useState(assignment?.title ?? "");
  const [type, setType] = useState<AssignmentType>(
    (assignment?.assignment_type as AssignmentType) ?? "ASSIGNMENT",
  );
  const [instructions, setInstructions] = useState(assignment?.instructions ?? "");
  const [kind, setKind] = useState<SubmissionKind>(
    (assignment?.submission_kind as SubmissionKind) ?? "LINK",
  );
  const [repoRequired, setRepoRequired] = useState(assignment?.repo_required ?? false);
  const [liveUrlExpected, setLiveUrlExpected] = useState(
    assignment?.live_url_expected ?? false,
  );
  const [isRequired, setIsRequired] = useState(assignment?.is_required ?? true);
  const [dueOffset, setDueOffset] = useState(
    assignment?.due_offset_days != null ? String(assignment.due_offset_days) : "",
  );
  const [maxScore, setMaxScore] = useState(
    assignment?.max_score != null ? String(assignment.max_score) : "",
  );
  const [linkedSkillId, setLinkedSkillId] = useState(assignment?.linked_skill_id ?? "");
  const [saving, setSaving] = useState(false);

  // Keep the CHECK satisfied client-side: turning on "requires a repo"
  // snaps a LINK/FILE/TEXT kind up to REPO.
  const effectiveKind: SubmissionKind =
    repoRequired && !REPO_KINDS.includes(kind) ? "REPO" : kind;

  const invalid = !title.trim();

  async function submit() {
    setSaving(true);
    try {
      await onSubmit({
        title: title.trim(),
        assignment_type: type,
        instructions: instructions.trim() ? instructions.trim() : null,
        submission_kind: effectiveKind,
        repo_required: repoRequired,
        live_url_expected: liveUrlExpected,
        is_required: isRequired,
        due_offset_days: dueOffset.trim() ? Number(dueOffset) : null,
        max_score: maxScore.trim() ? Number(maxScore) : null,
        linked_skill_id: linkedSkillId || null,
      });
    } catch {
      // The parent surfaces the failure in its top-level banner; the form
      // stays open so the industry user can retry.
    } finally {
      setSaving(false);
    }
  }

  const disabled = saving || busy;

  return (
    <div className="flex flex-col gap-3 rounded-lg border border-dashed p-3">
      <div className="grid gap-3 sm:grid-cols-[1fr_9rem]">
        <div className="space-y-1.5">
          <Label htmlFor="a-title">Assignment title</Label>
          <Input
            id="a-title"
            value={title}
            onChange={(e) => setTitle(e.target.value)}
            maxLength={200}
            disabled={disabled}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="a-type">Type</Label>
          <select
            id="a-type"
            className={SELECT_CLASS}
            value={type}
            onChange={(e) => setType(e.target.value as AssignmentType)}
            disabled={disabled}
          >
            {ASSIGNMENT_TYPES.map((t) => (
              <option key={t} value={t}>
                {ASSIGNMENT_TYPE_LABEL[t]}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="a-instructions">Instructions</Label>
        <Textarea
          id="a-instructions"
          value={instructions}
          onChange={(e) => setInstructions(e.target.value)}
          rows={3}
          maxLength={20000}
          disabled={disabled}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor="a-kind">What interns submit</Label>
        <select
          id="a-kind"
          className={SELECT_CLASS}
          value={effectiveKind}
          onChange={(e) => setKind(e.target.value as SubmissionKind)}
          disabled={disabled}
        >
          {SUBMISSION_KINDS.map((k) => (
            <option key={k} value={k}>
              {SUBMISSION_KIND_LABEL[k]}
            </option>
          ))}
        </select>
      </div>

      <div className="flex flex-wrap gap-x-5 gap-y-2 text-sm">
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={repoRequired}
            onChange={(e) => setRepoRequired(e.target.checked)}
            disabled={disabled}
          />
          Requires a code repository
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={liveUrlExpected}
            onChange={(e) => setLiveUrlExpected(e.target.checked)}
            disabled={disabled}
          />
          Expects a live / deployed URL
        </label>
        <label className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={isRequired}
            onChange={(e) => setIsRequired(e.target.checked)}
            disabled={disabled}
          />
          Required to complete the program
        </label>
      </div>

      <div className="grid gap-3 sm:grid-cols-3">
        <div className="space-y-1.5">
          <Label htmlFor="a-due">Due (days after start)</Label>
          <Input
            id="a-due"
            type="number"
            min={0}
            max={3650}
            value={dueOffset}
            onChange={(e) => setDueOffset(e.target.value)}
            disabled={disabled}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="a-score">Max score</Label>
          <Input
            id="a-score"
            type="number"
            min={1}
            value={maxScore}
            onChange={(e) => setMaxScore(e.target.value)}
            disabled={disabled}
          />
        </div>
        <div className="space-y-1.5">
          <Label htmlFor="a-skill">Linked skill</Label>
          <select
            id="a-skill"
            className={SELECT_CLASS}
            value={linkedSkillId}
            onChange={(e) => setLinkedSkillId(e.target.value)}
            disabled={disabled}
          >
            <option value="">None</option>
            {programSkills.map((s) => (
              <option key={s.skill_id} value={s.skill_id}>
                {s.skill_name}
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="flex gap-2">
        <Button size="sm" onClick={submit} disabled={disabled || invalid}>
          {saving && <Loader2 className="size-3.5 animate-spin" />}
          {assignment ? "Save assignment" : "Add assignment"}
        </Button>
        <Button size="sm" variant="ghost" onClick={onCancel} disabled={saving}>
          Cancel
        </Button>
      </div>
    </div>
  );
}
