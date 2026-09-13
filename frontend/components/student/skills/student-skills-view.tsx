"use client";

import { useEffect, useMemo, useState } from "react";
import { GraduationCap, Search } from "lucide-react";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormSuccess } from "@/components/auth/form-success";
import { AddSkillDialog } from "@/components/student/skills/add-skill-dialog";
import { EditSkillDialog } from "@/components/student/skills/edit-skill-dialog";
import { SkillCard } from "@/components/student/skill-card";
import { SkillSummary } from "@/components/student/skills/skill-summary";
import { SkillsToolbar } from "@/components/student/skills/skills-toolbar";
import { createClient } from "@/lib/supabase/client";
import { getAttemptHistory, listAssessments } from "@/lib/student/assessment";
import type { Assessment, AttemptHistoryItem } from "@/types/assessment";
import {
  addStudentSkill,
  deleteStudentSkill,
  getSkillErrorMessage,
  updateStudentSkillProficiency,
  type CatalogSkill,
  type ProficiencyLevel,
  type SkillCategory,
  type StudentSkill,
} from "@/lib/student/skills";

/** One assessment per (skill, difficulty) is the expected shape (see
 * assessments_skill_id_title_lower_idx in 004_assessments.sql, which
 * allows multiple titles per skill+difficulty in principle but the
 * product model is one) -- keyed by skill_id so a student's declared
 * proficiency_level (which uses the exact same 'Beginner'/'Intermediate'/
 * 'Advanced'/'Expert' scale as assessments.difficulty) can look up its
 * exact-match assessment directly. */
function keyFor(skillId: string, difficulty: string): string {
  return `${skillId}:${difficulty}`;
}

export function StudentSkillsView({
  studentId,
  initialStudentSkills,
  catalogSkills,
  categories,
}: {
  studentId: string;
  initialStudentSkills: StudentSkill[];
  catalogSkills: CatalogSkill[];
  categories: SkillCategory[];
}) {
  const [studentSkills, setStudentSkills] = useState(initialStudentSkills);
  const [search, setSearch] = useState("");
  const [categoryFilter, setCategoryFilter] = useState("all");

  // Matching assessment + latest attempt per (skill_id, difficulty) --
  // fetched once, client-side (the FastAPI bridge is browser-only, see
  // lib/api.ts), the same pattern AssessmentListView already uses.
  // listAssessments() is already scoped server-side to this student's
  // selected skills, and getAttemptHistory() to the caller's own attempts,
  // so every row either returns corresponds to one of the cards below; the
  // (skill_id, proficiency_level) exact-match lookup still decides which
  // card actually gets a "Verify Skill" action. Kept as an explicit
  // loading/error/ready state (rather than defaulting straight to empty
  // maps) so SkillCard can tell "still checking" and "the lookup itself
  // failed" apart from the honest "no assessment exists for this skill yet"
  // case -- collapsing all three into one silent empty-map state would make
  // every card claim "Assessment not available yet." during the initial
  // load and on a network failure, which is exactly the dishonest fallback
  // this feature is supposed to avoid.
  type AssessmentLookupState =
    | { status: "loading" }
    | { status: "error" }
    | {
        status: "ready";
        assessmentsByKey: Map<string, Assessment>;
        latestAttemptsByKey: Map<string, AttemptHistoryItem>;
      };

  const [assessmentLookup, setAssessmentLookup] = useState<AssessmentLookupState>({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    Promise.all([listAssessments(), getAttemptHistory()])
      .then(([{ assessments }, attempts]) => {
        if (cancelled) return;
        const assessmentsByKey = new Map(assessments.map((a) => [keyFor(a.skill_id, a.difficulty), a]));
        // getAttemptHistory() returns most-recent-first; keep only the
        // first (i.e. latest) attempt seen per (skill_id, difficulty) key.
        // An attempt whose assessment has since been deactivated comes
        // back with assessment: null (see list_own_attempts) -- it carries
        // no skill_id/difficulty to key by, so it's skipped here rather
        // than guessed at.
        const latestAttemptsByKey = new Map<string, AttemptHistoryItem>();
        for (const attempt of attempts) {
          if (!attempt.assessment) continue;
          const key = keyFor(attempt.assessment.skill_id, attempt.assessment.difficulty);
          if (!latestAttemptsByKey.has(key)) latestAttemptsByKey.set(key, attempt);
        }
        setAssessmentLookup({ status: "ready", assessmentsByKey, latestAttemptsByKey });
      })
      .catch((err) => {
        if (cancelled) return;
        console.error("Could not load assessments for skill matching:", err);
        setAssessmentLookup({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const [addOpen, setAddOpen] = useState(false);
  const [addSubmitting, setAddSubmitting] = useState(false);
  const [addError, setAddError] = useState<string | null>(null);

  const [editingSkill, setEditingSkill] = useState<StudentSkill | null>(null);
  const [editSubmitting, setEditSubmitting] = useState(false);
  const [editError, setEditError] = useState<string | null>(null);

  const [deletingSkill, setDeletingSkill] = useState<StudentSkill | null>(null);
  const [deleteSubmitting, setDeleteSubmitting] = useState(false);

  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const existingSkillIds = useMemo(() => new Set(studentSkills.map((s) => s.skill_id)), [studentSkills]);

  const visibleSkills = useMemo(() => {
    const query = search.trim().toLowerCase();
    return studentSkills.filter((studentSkill) => {
      const matchesSearch = !query || studentSkill.skill.name.toLowerCase().includes(query);
      const matchesCategory = categoryFilter === "all" || studentSkill.skill.category?.id === categoryFilter;
      return matchesSearch && matchesCategory;
    });
  }, [studentSkills, search, categoryFilter]);

  const summary = useMemo(() => {
    const total = studentSkills.length;
    const verified = studentSkills.filter((s) => s.is_verified).length;
    const advancedPlus = studentSkills.filter(
      (s) => s.proficiency_level === "Advanced" || s.proficiency_level === "Expert",
    ).length;
    return { total, verified, advancedPlus };
  }, [studentSkills]);

  async function handleAdd(skillId: string, proficiency: ProficiencyLevel) {
    setAddSubmitting(true);
    setAddError(null);
    setSuccessMessage(null);
    try {
      const supabase = createClient();
      const { data, error } = await addStudentSkill(supabase, studentId, {
        skillId,
        proficiencyLevel: proficiency,
      });
      if (error) {
        setAddError(getSkillErrorMessage(error));
        return;
      }
      const added = data as unknown as StudentSkill;
      setStudentSkills((prev) => [added, ...prev]);
      setAddOpen(false);
      setSuccessMessage(`${added.skill.name} added to your skills.`);
    } catch (err) {
      console.error("Add skill failed:", err);
      setAddError(getSkillErrorMessage(err));
    } finally {
      setAddSubmitting(false);
    }
  }

  async function handleUpdateProficiency(proficiency: ProficiencyLevel) {
    if (!editingSkill) return;
    setEditSubmitting(true);
    setEditError(null);
    setSuccessMessage(null);
    try {
      const supabase = createClient();
      const { data, error } = await updateStudentSkillProficiency(supabase, studentId, editingSkill.id, proficiency);
      if (error) {
        setEditError(getSkillErrorMessage(error));
        return;
      }
      const updated = data as unknown as StudentSkill;
      setStudentSkills((prev) => prev.map((s) => (s.id === updated.id ? updated : s)));
      setEditingSkill(null);
      setSuccessMessage(`${updated.skill.name} updated.`);
    } catch (err) {
      console.error("Update skill failed:", err);
      setEditError(getSkillErrorMessage(err));
    } finally {
      setEditSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!deletingSkill) return;
    setDeleteSubmitting(true);
    setSuccessMessage(null);
    try {
      const supabase = createClient();
      const { error } = await deleteStudentSkill(supabase, studentId, deletingSkill.id);
      if (error) {
        console.error("Delete skill failed:", error.message);
        return;
      }
      setStudentSkills((prev) => prev.filter((s) => s.id !== deletingSkill.id));
      setSuccessMessage(`${deletingSkill.skill.name} removed from your skills.`);
      setDeletingSkill(null);
    } catch (err) {
      console.error("Delete skill failed:", err);
    } finally {
      setDeleteSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">My Skills</h1>
        <p className="text-sm text-muted-foreground">Build and manage your professional skill profile.</p>
      </div>

      <FormSuccess message={successMessage} />

      <SkillSummary total={summary.total} verified={summary.verified} advancedPlus={summary.advancedPlus} />

      <SkillsToolbar
        search={search}
        onSearchChange={setSearch}
        categoryId={categoryFilter}
        onCategoryChange={setCategoryFilter}
        categories={categories}
        onAddClick={() => setAddOpen(true)}
      />

      {studentSkills.length === 0 ? (
        <EmptyState
          icon={GraduationCap}
          title="No skills added yet"
          description="Add your technical and professional skills to build your skill profile."
          actionLabel="+ Add Your First Skill"
          onAction={() => setAddOpen(true)}
        />
      ) : visibleSkills.length === 0 ? (
        <EmptyState icon={Search} title="No skills match your search" description="Try a different search term or category filter." />
      ) : (
        <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
          {visibleSkills.map((studentSkill) => {
            const key = keyFor(studentSkill.skill_id, studentSkill.proficiency_level);
            return (
              <SkillCard
                key={studentSkill.id}
                studentSkill={studentSkill}
                lookupStatus={assessmentLookup.status}
                matchingAssessment={assessmentLookup.status === "ready" ? assessmentLookup.assessmentsByKey.get(key) : undefined}
                latestAttempt={assessmentLookup.status === "ready" ? assessmentLookup.latestAttemptsByKey.get(key) : undefined}
                onEdit={() => setEditingSkill(studentSkill)}
                onDelete={() => setDeletingSkill(studentSkill)}
              />
            );
          })}
        </div>
      )}

      <AddSkillDialog
        open={addOpen}
        onOpenChange={setAddOpen}
        catalogSkills={catalogSkills}
        categories={categories}
        existingSkillIds={existingSkillIds}
        submitting={addSubmitting}
        error={addError}
        onAdd={handleAdd}
      />

      <EditSkillDialog
        studentSkill={editingSkill}
        onOpenChange={(open) => !open && setEditingSkill(null)}
        submitting={editSubmitting}
        error={editError}
        onSave={handleUpdateProficiency}
      />

      <ConfirmationDialog
        open={!!deletingSkill}
        onOpenChange={(open) => !open && setDeletingSkill(null)}
        title={`Remove ${deletingSkill?.skill.name ?? "this skill"} from your skills?`}
        description="This can't be undone. You can add it again later if needed."
        confirmLabel="Remove Skill"
        destructive
        loading={deleteSubmitting}
        onConfirm={handleDelete}
      />
    </div>
  );
}
