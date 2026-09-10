"use client";

import { useId, useState } from "react";
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
import {
  TRAINING_WORK_MODES,
  TRAINING_WORK_MODE_LABELS,
  type IndustryTraining,
  type TrainingCreate,
  type TrainingWorkMode,
} from "@/types/industry-training";

const UNSET = "__unset__";

interface FieldErrors {
  title?: string;
  description?: string;
  durationMonths?: string;
  capacity?: string;
  applicationDeadline?: string;
}

function toFormState(initial?: IndustryTraining) {
  return {
    title: initial?.title ?? "",
    description: initial?.description ?? "",
    location: initial?.location ?? "",
    workMode: (initial?.work_mode ?? null) as TrainingWorkMode | null,
    durationMonths: initial?.duration_months?.toString() ?? "",
    capacity: initial?.capacity?.toString() ?? "",
    eligibilityCriteria: initial?.eligibility_criteria ?? "",
    applicationDeadline: initial?.application_deadline ?? "",
    startDate: initial?.start_date ?? "",
  };
}

type FormState = ReturnType<typeof toFormState>;

const textareaClass =
  "w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30";

export function TrainingForm({
  mode,
  initial,
  submitting,
  error,
  onSubmit,
  onCancel,
}: {
  mode: "create" | "edit";
  initial?: IndustryTraining;
  submitting: boolean;
  error: string | null;
  onSubmit: (data: TrainingCreate) => void;
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
    capacity: useId(),
    eligibilityCriteria: useId(),
    applicationDeadline: useId(),
    startDate: useId(),
  };

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
    if (form.capacity.trim()) {
      const n = Number(form.capacity);
      if (!Number.isInteger(n) || n < 1) errors.capacity = "Enter a whole number of 1 or more.";
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

    const data: TrainingCreate = {
      title: form.title.trim(),
      description: form.description.trim(),
      location: form.location.trim() || null,
      work_mode: form.workMode,
      duration_months: form.durationMonths.trim() ? Number(form.durationMonths) : null,
      capacity: form.capacity.trim() ? Number(form.capacity) : null,
      eligibility_criteria: form.eligibilityCriteria.trim() || null,
      application_deadline: form.applicationDeadline || null,
      start_date: form.startDate || null,
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
              placeholder="e.g. Cloud Fundamentals Bootcamp"
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
              placeholder="Curriculum, format, what trainees will learn..."
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
          <CardTitle>Training Details</CardTitle>
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
              value={form.workMode ?? UNSET}
              onValueChange={(next) =>
                set("workMode", next === UNSET ? null : (next as TrainingWorkMode))
              }
              disabled={submitting}
            >
              <SelectTrigger id={ids.workMode} className="w-full">
                <SelectValue placeholder="Not specified" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={UNSET}>Not specified</SelectItem>
                {TRAINING_WORK_MODES.map((m) => (
                  <SelectItem key={m} value={m}>
                    {TRAINING_WORK_MODE_LABELS[m]}
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
              placeholder="e.g. 2"
              disabled={submitting}
              aria-invalid={!!fieldErrors.durationMonths}
            />
            <FieldError id={`${ids.durationMonths}-error`} message={fieldErrors.durationMonths} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.capacity}>Capacity</Label>
            <Input
              id={ids.capacity}
              inputMode="numeric"
              value={form.capacity}
              onChange={(e) => set("capacity", e.target.value)}
              placeholder="e.g. 30"
              disabled={submitting}
              aria-invalid={!!fieldErrors.capacity}
            />
            <FieldError id={`${ids.capacity}-error`} message={fieldErrors.capacity} />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Timeline & Eligibility</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
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
              placeholder="Year of study, prerequisite skills, prior experience..."
              disabled={submitting}
              className={textareaClass}
            />
          </div>
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
