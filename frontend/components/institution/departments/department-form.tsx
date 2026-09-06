"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FormError } from "@/components/auth/form-error";
import { ApiError } from "@/lib/api";
import { createInstitutionDepartment, updateInstitutionDepartment } from "@/lib/institution/departments";
import type { DepartmentSummary } from "@/types/institution-department";

/**
 * One dialog, two modes: `department` absent creates a new department
 * (always active by default, no status control); `department` present
 * edits it (adds the Active/Inactive control -- deactivation, never a
 * delete endpoint exists, see backend/app/api/institution.py).
 */
export function DepartmentForm({
  open,
  onOpenChange,
  department,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  department?: DepartmentSummary;
  onSaved: (department: DepartmentSummary) => void;
}) {
  const [name, setName] = useState(department?.name ?? "");
  const [code, setCode] = useState(department?.code ?? "");
  const [description, setDescription] = useState(department?.description ?? "");
  const [isActive, setIsActive] = useState(department?.is_active ?? true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nameId = useId();
  const codeId = useId();
  const descriptionId = useId();
  const statusId = useId();

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!name.trim()) {
      setError("Department name is required.");
      return;
    }
    setSubmitting(true);
    try {
      const saved = department
        ? await updateInstitutionDepartment(department.id, {
            name: name.trim(),
            code: code.trim() || null,
            description: description.trim() || null,
            is_active: isActive,
          })
        : await createInstitutionDepartment({
            name: name.trim(),
            code: code.trim() || null,
            description: description.trim() || null,
          });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the department. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{department ? "Edit Department" : "Add Department"}</DialogTitle>
            <DialogDescription>
              Departments organize your institution&apos;s students and placement analytics.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <FormError message={error} />

            <div className="space-y-1.5">
              <Label htmlFor={nameId}>Name</Label>
              <Input
                id={nameId}
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. Computer Science & Engineering"
                maxLength={200}
                disabled={submitting}
                autoFocus
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={codeId}>Code (optional)</Label>
              <Input
                id={codeId}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="e.g. CSE"
                maxLength={40}
                disabled={submitting}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={descriptionId}>Description (optional)</Label>
              <Textarea
                id={descriptionId}
                value={description}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                maxLength={2000}
                disabled={submitting}
              />
            </div>

            {department ? (
              <div className="space-y-1.5">
                <Label htmlFor={statusId}>Status</Label>
                <Select
                  value={isActive ? "active" : "inactive"}
                  onValueChange={(v) => setIsActive(v !== "inactive")}
                  disabled={submitting}
                >
                  <SelectTrigger id={statusId} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Deactivating a department does not remove its students or their placement history.
                </p>
              </div>
            ) : null}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving..." : department ? "Save Changes" : "Add Department"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
