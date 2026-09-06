"use client";

import { useId, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { SkillRequirementsPicker } from "@/components/industry/skill-requirements-picker";
import type { CatalogSkill } from "@/lib/industry/skills";
import {
  EMPLOYMENT_TYPES,
  EMPLOYMENT_TYPE_LABELS,
  WORK_MODES,
  WORK_MODE_LABELS,
  type EmploymentType,
  type Job,
  type JobCreate,
  type JobSkillInput,
  type WorkMode,
} from "@/types/job";

const UNSET = "__unset__";

interface FieldErrors {
  title?: string;
  description?: string;
  experienceMinYears?: string;
  salaryMin?: string;
  salaryMax?: string;
  openings?: string;
  applicationDeadline?: string;
}

function toFormState(initial?: Job) {
  return {
    title: initial?.title ?? "",
    description: initial?.description ?? "",
    location: initial?.location ?? "",
    employmentType: (initial?.employment_type ?? null) as EmploymentType | null,
    workMode: (initial?.work_mode ?? null) as WorkMode | null,
    experienceMinYears: initial?.experience_min_years?.toString() ?? "",
    salaryMin: initial?.salary_min?.toString() ?? "",
    salaryMax: initial?.salary_max?.toString() ?? "",
    salaryCurrency: initial?.salary_currency ?? "INR",
    openings: initial?.openings?.toString() ?? "1",
    eligibilityCriteria: initial?.eligibility_criteria ?? "",
    applicationDeadline: initial?.application_deadline ?? "",
    skills: (initial?.skills ?? []).map((s) => ({
      skill_id: s.skill_id,
      required_level: s.required_level,
      importance: s.importance,
    })) as JobSkillInput[],
  };
}

type FormState = ReturnType<typeof toFormState>;

const textareaClass =
  "w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30";

export function JobForm({
  mode,
  catalog,
  initial,
  submitting,
  error,
  onSubmit,
  onCancel,
}: {
  mode: "create" | "edit";
  catalog: CatalogSkill[];
  initial?: Job;
  submitting: boolean;
  error: string | null;
  onSubmit: (data: JobCreate) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<FormState>(() => toFormState(initial));
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const ids = {
    title: useId(),
    description: useId(),
    location: useId(),
    employmentType: useId(),
    workMode: useId(),
    experienceMinYears: useId(),
    salaryMin: useId(),
    salaryMax: useId(),
    salaryCurrency: useId(),
    openings: useId(),
    eligibilityCriteria: useId(),
    applicationDeadline: useId(),
  };

  const catalogById = useMemo(() => new Map(catalog.map((s) => [s.id, s])), [catalog]);

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const errors: FieldErrors = {};
    if (!form.title.trim()) errors.title = "A title is required.";
    if (form.title.trim().length > 200) errors.title = "Keep the title under 200 characters.";
    if (!form.description.trim()) errors.description = "A description is required.";

    if (form.experienceMinYears.trim()) {
      const n = Number(form.experienceMinYears);
      if (Number.isNaN(n) || n < 0 || n > 99.9) {
        errors.experienceMinYears = "Enter a number of years between 0 and 99.9.";
      }
    }
    const min = form.salaryMin.trim() ? Number(form.salaryMin) : null;
    const max = form.salaryMax.trim() ? Number(form.salaryMax) : null;
    if (min !== null && (Number.isNaN(min) || min < 0)) errors.salaryMin = "Enter a non-negative amount.";
    if (max !== null && (Number.isNaN(max) || max < 0)) errors.salaryMax = "Enter a non-negative amount.";
    if (min !== null && max !== null && !Number.isNaN(min) && !Number.isNaN(max) && max < min) {
      errors.salaryMax = "Maximum can't be lower than the minimum.";
    }
    if (form.openings.trim()) {
      const n = Number(form.openings);
      if (!Number.isInteger(n) || n < 1) errors.openings = "Enter a whole number of 1 or more.";
    }
    if (form.applicationDeadline.trim() && Number.isNaN(Date.parse(form.applicationDeadline))) {
      errors.applicationDeadline = "Enter a valid date.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting || !validate()) return;

    const data: JobCreate = {
      title: form.title.trim(),
      description: form.description.trim(),
      location: form.location.trim() || null,
      work_mode: form.workMode,
      employment_type: form.employmentType,
      salary_min: form.salaryMin.trim() ? Number(form.salaryMin) : null,
      salary_max: form.salaryMax.trim() ? Number(form.salaryMax) : null,
      salary_currency: form.salaryCurrency.trim() || null,
      experience_min_years: form.experienceMinYears.trim() ? Number(form.experienceMinYears) : null,
      openings: form.openings.trim() ? Number(form.openings) : null,
      eligibility_criteria: form.eligibilityCriteria.trim() || null,
      application_deadline: form.applicationDeadline || null,
      skills: form.skills.filter((s) => catalogById.has(s.skill_id)),
    };
    onSubmit(data);
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">
      <FormError message={error} />

      <Card>
        <CardHeader>
          <CardTitle>Basic Information</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor={ids.title}>Title</Label>
            <Input
              id={ids.title}
              value={form.title}
              onChange={(e) => set("title", e.target.value)}
              maxLength={200}
              placeholder="e.g. Backend Engineer"
              disabled={submitting}
              aria-invalid={!!fieldErrors.title}
            />
            <FieldError id={`${ids.title}-error`} message={fieldErrors.title} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.description}>Description</Label>
            <textarea
              id={ids.description}
              value={form.description}
              onChange={(e) => set("description", e.target.value)}
              rows={5}
              maxLength={10000}
              placeholder="Responsibilities, team, tech stack, growth path..."
              disabled={submitting}
              className={textareaClass}
              aria-invalid={!!fieldErrors.description}
            />
            <FieldError id={`${ids.description}-error`} message={fieldErrors.description} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Job Details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={ids.location}>Location</Label>
            <Input
              id={ids.location}
              value={form.location}
              onChange={(e) => set("location", e.target.value)}
              maxLength={200}
              placeholder="e.g. Pune, India"
              disabled={submitting}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.employmentType}>Employment Type</Label>
            <Select
              value={form.employmentType ?? UNSET}
              onValueChange={(next) =>
                set("employmentType", next === UNSET ? null : (next as EmploymentType))
              }
              disabled={submitting}
            >
              <SelectTrigger id={ids.employmentType} className="w-full">
                <SelectValue placeholder="Not specified" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={UNSET}>Not specified</SelectItem>
                {EMPLOYMENT_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {EMPLOYMENT_TYPE_LABELS[t]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.workMode}>Work Mode</Label>
            <Select
              value={form.workMode ?? UNSET}
              onValueChange={(next) => set("workMode", next === UNSET ? null : (next as WorkMode))}
              disabled={submitting}
            >
              <SelectTrigger id={ids.workMode} className="w-full">
                <SelectValue placeholder="Not specified" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={UNSET}>Not specified</SelectItem>
                {WORK_MODES.map((m) => (
                  <SelectItem key={m} value={m}>
                    {WORK_MODE_LABELS[m]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.experienceMinYears}>Minimum Experience (years)</Label>
            <Input
              id={ids.experienceMinYears}
              inputMode="decimal"
              value={form.experienceMinYears}
              onChange={(e) => set("experienceMinYears", e.target.value)}
              placeholder="e.g. 2"
              disabled={submitting}
              aria-invalid={!!fieldErrors.experienceMinYears}
            />
            <FieldError
              id={`${ids.experienceMinYears}-error`}
              message={fieldErrors.experienceMinYears}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Compensation</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-3">
          <div className="space-y-1.5">
            <Label htmlFor={ids.salaryMin}>Salary (min)</Label>
            <Input
              id={ids.salaryMin}
              inputMode="decimal"
              value={form.salaryMin}
              onChange={(e) => set("salaryMin", e.target.value)}
              placeholder="e.g. 1800000"
              disabled={submitting}
              aria-invalid={!!fieldErrors.salaryMin}
            />
            <FieldError id={`${ids.salaryMin}-error`} message={fieldErrors.salaryMin} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.salaryMax}>Salary (max)</Label>
            <Input
              id={ids.salaryMax}
              inputMode="decimal"
              value={form.salaryMax}
              onChange={(e) => set("salaryMax", e.target.value)}
              placeholder="e.g. 2600000"
              disabled={submitting}
              aria-invalid={!!fieldErrors.salaryMax}
            />
            <FieldError id={`${ids.salaryMax}-error`} message={fieldErrors.salaryMax} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.salaryCurrency}>Currency</Label>
            <Input
              id={ids.salaryCurrency}
              value={form.salaryCurrency}
              onChange={(e) => set("salaryCurrency", e.target.value.toUpperCase())}
              maxLength={8}
              placeholder="INR"
              disabled={submitting}
            />
          </div>
          <p className="text-xs text-muted-foreground sm:col-span-3">
            Annual salary range. Both fields are optional.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Recruitment</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={ids.openings}>Openings</Label>
            <Input
              id={ids.openings}
              inputMode="numeric"
              value={form.openings}
              onChange={(e) => set("openings", e.target.value)}
              placeholder="e.g. 3"
              disabled={submitting}
              aria-invalid={!!fieldErrors.openings}
            />
            <FieldError id={`${ids.openings}-error`} message={fieldErrors.openings} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.applicationDeadline}>Application Deadline</Label>
            <Input
              id={ids.applicationDeadline}
              type="date"
              value={form.applicationDeadline}
              onChange={(e) => set("applicationDeadline", e.target.value)}
              disabled={submitting}
              aria-invalid={!!fieldErrors.applicationDeadline}
            />
            <FieldError
              id={`${ids.applicationDeadline}-error`}
              message={fieldErrors.applicationDeadline}
            />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor={ids.eligibilityCriteria}>Eligibility Criteria</Label>
            <textarea
              id={ids.eligibilityCriteria}
              value={form.eligibilityCriteria}
              onChange={(e) => set("eligibilityCriteria", e.target.value)}
              rows={3}
              maxLength={5000}
              placeholder="Degree, prior experience, portfolio expectations..."
              disabled={submitting}
              className={textareaClass}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Required Skills</CardTitle>
        </CardHeader>
        <CardContent>
          <SkillRequirementsPicker
            catalog={catalog}
            value={form.skills}
            onChange={(next) => set("skills", next)}
            disabled={submitting}
          />
          <p className="mt-3 text-xs text-muted-foreground">
            At least one skill is required before a job can be published.
          </p>
        </CardContent>
      </Card>

      <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
        <Button
          type="button"
          variant="outline"
          className="sm:w-auto"
          onClick={onCancel}
          disabled={submitting}
        >
          Cancel
        </Button>
        <Button type="submit" className="sm:w-auto" disabled={submitting}>
          {submitting ? "Saving..." : mode === "create" ? "Save Draft" : "Save Changes"}
        </Button>
      </div>
    </form>
  );
}
