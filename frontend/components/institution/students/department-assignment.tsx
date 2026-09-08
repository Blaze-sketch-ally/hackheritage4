"use client";

import { useEffect, useState } from "react";
import { Landmark } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FormError } from "@/components/auth/form-error";
import { ApiError } from "@/lib/api";
import { assignStudentDepartment, getInstitutionDepartments } from "@/lib/institution/departments";
import type { DepartmentSummary } from "@/types/institution-department";
import type { StudentDetail } from "@/types/institution-student";

const UNASSIGNED = "__unassigned__";

/**
 * Lets the institution reassign (or clear) which of ITS OWN departments a
 * linked student belongs to. Both sides of the assignment are enforced
 * server-side (institution_department_service.assign_student_department)
 * -- this control only ever offers the institution's own departments,
 * never a cross-institution id.
 */
export function DepartmentAssignment({
  student,
  onStudentUpdated,
}: {
  student: StudentDetail;
  onStudentUpdated: (student: StudentDetail) => void;
}) {
  const [departments, setDepartments] = useState<DepartmentSummary[] | null>(null);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getInstitutionDepartments()
      .then(({ departments: rows }) => {
        if (!cancelled) setDepartments(rows);
      })
      .catch(() => {
        if (!cancelled) setDepartments([]);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleChange(value: string) {
    setError(null);
    const departmentId = value === UNASSIGNED ? null : value;
    setSaving(true);
    try {
      const updated = await assignStudentDepartment(student.id, departmentId);
      onStudentUpdated(updated);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not update the department.");
    } finally {
      setSaving(false);
    }
  }

  // Always include the student's CURRENT department in the option list,
  // even if it has since been deactivated -- otherwise the Select would
  // silently show nothing selected for a real, historical assignment.
  const options = [...(departments ?? [])];
  if (student.department_id && !options.some((d) => d.id === student.department_id)) {
    options.push({
      id: student.department_id,
      name: student.department,
      code: null,
      description: null,
      is_active: false,
      created_at: null,
      updated_at: null,
      student_count: 0,
      placed_count: 0,
      unplaced_count: 0,
      no_applications_count: 0,
      placement_rate: null,
      internship_selected_count: 0,
    });
  }

  return (
    <div className="space-y-1.5 border-b pb-4">
      <p className="flex items-center gap-1.5 text-xs font-medium text-muted-foreground">
        <Landmark className="size-3.5" aria-hidden="true" /> Department
      </p>
      <FormError message={error} />
      <Select
        value={student.department_id ?? UNASSIGNED}
        onValueChange={(v) => handleChange(v ?? UNASSIGNED)}
        disabled={departments === null || saving}
      >
        <SelectTrigger className="w-full" aria-label="Department">
          <SelectValue />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={UNASSIGNED}>Unassigned</SelectItem>
          {options.map((d) => (
            <SelectItem key={d.id} value={d.id}>
              {d.name}
              {d.is_active ? "" : " (inactive)"}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
      {student.self_reported_department ? (
        <p className="text-xs text-muted-foreground">
          Student&apos;s own profile lists: &quot;{student.self_reported_department}&quot;
        </p>
      ) : null}
    </div>
  );
}
