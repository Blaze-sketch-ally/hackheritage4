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
  WORK_MODES,
  WORK_MODE_LABELS,
  type Internship,
  type InternshipCreate,
  type InternshipSkillInput,
  type WorkMode,
} from "@/types/internship";

const WM_UNSET = "__unset__";

interface FieldErrors {
  title?: string;
  description?: string;
  durationMonths?: string;
  stipendAmount?: string;
  openings?: string;
  applicationDeadline?: string;
}

function toFormState(initial?: Internship) {
  return {
    title: initial?.title ?? "",
    description: initial?.description ?? "",
    location: initial?.location ?? "",
    workMode: (initial?.work_mode ?? null) as WorkMode | null,
    durationMonths: initial?.duration_months?.toString() ?? "",
    stipendAmount: initial?.stipend_amount?.toString() ?? "",
    stipendCurrency: initial?.stipend_currency ?? "INR",
    openings: initial?.openings?.toString() ?? "1",
    eligibilityCriteria: initial?.eligibility_criteria ?? "",
    applicationDeadline: initial?.application_deadline ?? "",
    startDate: initial?.start_date ?? "",
    skills: (initial?.skills ?? []).map((s) => ({
      skill_id: s.skill_id,
      required_level: s.required_level,
      importance: s.importance,
    })) as InternshipSkillInput[],
  };
}

type FormState = ReturnType<typeof toFormState>;

const textareaClass =
  "w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30";

export function InternshipForm({
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
  initial?: Internship;
  submitting: boolean;
  error: string | null;
  onSubmit: (data: InternshipCreate) => void;
  onCancel: () => void;
}) {
  const [form, setForm] = useState<FormState>(() => toFormState(initial));
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const ids = {
    title: useId(),
    description: useId(),
    location: useId(),
    workMode: useId(),
    durationMonths: useId(),
    openings: useId(),
    stipendAmount: useId(),
    stipendCurrency: useId(),
    applicationDeadline: useId(),
    startDate: useId(),
    eligibilityCriteria: useId(),
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

    if (form.durationMonths.trim()) {
      const n = Number(form.durationMonths);
      if (!Number.isInteger(n) || n < 1 || n > 24) {
        errors.durationMonths = "Enter a whole number of months between 1 and 24.";
      }
    }
    if (form.stipendAmount.trim()) {
      const n = Number(form.stipendAmount);
      if (Number.isNaN(n) || n < 0) errors.stipendAmount = "Enter a non-negative amount.";
    }
    if (form.openings.trim()) {
      const n = Number(form.openings);
      if (!Number.isInteger(n) || n < 1) errors.openings = "Enter a whole number of 1 or more.";
    }
    if (form.applicationDeadline.trim()) {
      const parsed = Date.parse(form.applicationDeadline);
      if (Number.isNaN(parsed)) errors.applicationDeadline = "Enter a valid date.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting || !validate()) return;

    const data: InternshipCreate = {
      title: form.title.trim(),
      description: form.description.trim(),
      location: form.location.trim() || null,
      work_mode: form.workMode,
      duration_months: form.durationMonths.trim() ? Number(form.durationMonths) : null,
      stipend_amount: form.stipendAmount.trim() ? Number(form.stipendAmount) : null,
      stipend_currency: form.stipendCurrency.trim() || null,
      openings: form.openings.trim() ? Number(form.openings) : null,
      eligibility_criteria: form.eligibilityCriteria.trim() || null,
      application_deadline: form.applicationDeadline || null,
      start_date: form.startDate || null,
      // Drop any selected skill that's no longer in the catalog.
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
              placeholder="e.g. Backend Engineering Intern"
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
              placeholder="Responsibilities, team, what the intern will learn..."
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
          <CardTitle>Internship Details</CardTitle>
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
            <Label htmlFor={ids.workMode}>Work Mode</Label>
            <Select
              value={form.workMode ?? WM_UNSET}
              onValueChange={(next) => set("workMode", next === WM_UNSET ? null : (next as WorkMode))}
              disabled={submitting}
            >
              <SelectTrigger id={ids.workMode} className="w-full">
                <SelectValue placeholder="Not specified" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={WM_UNSET}>Not specified</SelectItem>
                {WORK_MODES.map((mode) => (
                  <SelectItem key={mode} value={mode}>
                    {WORK_MODE_LABELS[mode]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.durationMonths}>Duration (months)</Label>
            <Input
              id={ids.durationMonths}
              inputMode="numeric"
              value={form.durationMonths}
              onChange={(e) => set("durationMonths", e.target.value)}
              placeholder="e.g. 6"
              disabled={submitting}
              aria-invalid={!!fieldErrors.durationMonths}
            />
            <FieldError id={`${ids.durationMonths}-error`} message={fieldErrors.durationMonths} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.openings}>Openings</Label>
            <Input
              id={ids.openings}
              inputMode="numeric"
              value={form.openings}
              onChange={(e) => set("openings", e.target.value)}
              placeholder="e.g. 2"
              disabled={submitting}
              aria-invalid={!!fieldErrors.openings}
            />
            <FieldError id={`${ids.openings}-error`} message={fieldErrors.openings} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Compensation</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={ids.stipendAmount}>Monthly Stipend</Label>
            <Input
              id={ids.stipendAmount}
              inputMode="decimal"
              value={form.stipendAmount}
              onChange={(e) => set("stipendAmount", e.target.value)}
              placeholder="e.g. 15000"
              disabled={submitting}
              aria-invalid={!!fieldErrors.stipendAmount}
            />
            <FieldError id={`${ids.stipendAmount}-error`} message={fieldErrors.stipendAmount} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.stipendCurrency}>Currency</Label>
            <Input
              id={ids.stipendCurrency}
              value={form.stipendCurrency}
              onChange={(e) => set("stipendCurrency", e.target.value.toUpperCase())}
              maxLength={8}
              placeholder="INR"
              disabled={submitting}
            />
            <p className="text-xs text-muted-foreground">
              The schema stores a single monthly stipend, not a min/max range.
            </p>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Application</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
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
          <div className="space-y-1.5">
            <Label htmlFor={ids.startDate}>Start Date</Label>
            <Input
              id={ids.startDate}
              type="date"
              value={form.startDate}
              onChange={(e) => set("startDate", e.target.value)}
              disabled={submitting}
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
              placeholder="Year of study, prior experience, portfolio expectations..."
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
            At least one skill is required before an internship can be published.
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
