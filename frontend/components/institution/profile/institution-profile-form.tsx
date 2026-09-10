"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { ApiError } from "@/lib/api";
import { updateInstitutionProfile } from "@/lib/institution/profile";
import { isValidPhone, isValidUrl } from "@/lib/validations";
import type { InstitutionProfile, InstitutionProfileFields } from "@/types/institution";

interface FieldErrors {
  websiteUrl?: string;
  contactPhone?: string;
}

function toFormState(profile: InstitutionProfile) {
  return {
    institutionName: profile.institution_name ?? "",
    institutionType: profile.institution_type ?? "",
    location: profile.location ?? "",
    websiteUrl: profile.website_url ?? "",
    contactPhone: profile.contact_phone ?? "",
  };
}

type FormState = ReturnType<typeof toFormState>;

export function InstitutionProfileForm({
  profile,
  onCancel,
  onSaved,
}: {
  profile: InstitutionProfile;
  onCancel: () => void;
  onSaved: (updated: InstitutionProfile) => void;
}) {
  const [form, setForm] = useState<FormState>(() => toFormState(profile));
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const ids = {
    institutionName: useId(),
    institutionType: useId(),
    location: useId(),
    websiteUrl: useId(),
    contactPhone: useId(),
  };

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const errors: FieldErrors = {};
    if (form.contactPhone.trim() && !isValidPhone(form.contactPhone)) {
      errors.contactPhone = "7–20 characters: digits, spaces, +, -, or parentheses.";
    }
    if (form.websiteUrl.trim() && !isValidUrl(form.websiteUrl)) {
      errors.websiteUrl = "Enter a full URL starting with http:// or https://";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (submitting || !validate()) return;
    setSubmitting(true);

    const fields: InstitutionProfileFields = {
      institution_name: form.institutionName.trim() || null,
      institution_type: form.institutionType.trim() || null,
      location: form.location.trim() || null,
      website_url: form.websiteUrl.trim() || null,
      contact_phone: form.contactPhone.trim() || null,
    };

    try {
      const updated = await updateInstitutionProfile(fields);
      onSaved(updated);
    } catch (err) {
      setFormError(
        err instanceof ApiError
          ? err.message
          : "Unable to save your institution profile. Please try again.",
      );
      setSubmitting(false);
    }
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">
      <FormError message={formError} />

      <Card>
        <CardHeader>
          <CardTitle>Institution Details</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={ids.institutionName}>Institution Name</Label>
            <Input
              id={ids.institutionName}
              value={form.institutionName}
              onChange={(e) => set("institutionName", e.target.value)}
              maxLength={200}
              placeholder="e.g. State College of Engineering"
              disabled={submitting}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.institutionType}>Institution Type</Label>
            <Input
              id={ids.institutionType}
              value={form.institutionType}
              onChange={(e) => set("institutionType", e.target.value)}
              maxLength={120}
              placeholder="e.g. Government, Private, Autonomous"
              disabled={submitting}
            />
          </div>
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
            <Label htmlFor={ids.websiteUrl}>Website</Label>
            <Input
              id={ids.websiteUrl}
              type="url"
              value={form.websiteUrl}
              onChange={(e) => set("websiteUrl", e.target.value)}
              placeholder="https://..."
              disabled={submitting}
              aria-invalid={!!fieldErrors.websiteUrl}
            />
            <FieldError id={`${ids.websiteUrl}-error`} message={fieldErrors.websiteUrl} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.contactPhone}>Contact Phone</Label>
            <Input
              id={ids.contactPhone}
              type="tel"
              value={form.contactPhone}
              onChange={(e) => set("contactPhone", e.target.value)}
              placeholder="+91 20 1234 5678"
              disabled={submitting}
              aria-invalid={!!fieldErrors.contactPhone}
            />
            <FieldError id={`${ids.contactPhone}-error`} message={fieldErrors.contactPhone} />
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
          {submitting ? "Saving..." : "Save Changes"}
        </Button>
      </div>
    </form>
  );
}
