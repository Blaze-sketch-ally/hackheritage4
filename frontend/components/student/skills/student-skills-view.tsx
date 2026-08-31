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
import { listAssessments } from "@/lib/student/assessment";
import type { Assessment } from "@/types/assessment";
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

  // Matching assessment per (skill_id, difficulty) -- fetched once,
  // client-side (the FastAPI bridge is browser-only, see lib/api.ts), the
  // same pattern AssessmentListView already uses. A failure here degrades
  // gracefully to "Assessment not available yet." on every card rather
  // than blocking the skills page itself.
  const [assessmentsByKey, setAssessmentsByKey] = useState<Map<string, Assessment>>(new Map());

  useEffect(() => {
    let cancelled = false;
    listAssessments()
      .then(({ assessments }) => {
        if (cancelled) return;
        setAssessmentsByKey(new Map(assessments.map((a) => [keyFor(a.skill_id, a.difficulty), a])));
      })
      .catch((err) => {
        console.error("Could not load assessments for skill matching:", err);
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
          {visibleSkills.map((studentSkill) => (
            <SkillCard
              key={studentSkill.id}
              studentSkill={studentSkill}
              matchingAssessment={assessmentsByKey.get(keyFor(studentSkill.skill_id, studentSkill.proficiency_level))}
              onEdit={() => setEditingSkill(studentSkill)}
              onDelete={() => setDeletingSkill(studentSkill)}
            />
          ))}
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
