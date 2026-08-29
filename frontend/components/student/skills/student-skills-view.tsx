"use client";

import { useMemo, useState } from "react";
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
