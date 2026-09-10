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
import { ApiError } from "@/lib/api";
import { updateIndustryProfile } from "@/lib/industry/profile";
import { isValidPhone, isValidUrl } from "@/lib/validations";
import {
  COMPANY_SIZES,
  COMPANY_SIZE_LABELS,
  type CompanySize,
  type IndustryProfile,
  type IndustryProfileFields,
} from "@/types/industry";

const SIZE_UNSET = "__unset__";
const CURRENT_YEAR = new Date().getFullYear();

interface FieldErrors {
  foundedYear?: string;
  websiteUrl?: string;
  linkedinUrl?: string;
  contactPhone?: string;
  logoUrl?: string;
}

function toFormState(profile: IndustryProfile) {
  return {
    companyName: profile.company_name ?? "",
    industrySector: profile.industry_sector ?? "",
    companySize: profile.company_size,
    foundedYear: profile.founded_year?.toString() ?? "",
    companyDescription: profile.company_description ?? "",
    websiteUrl: profile.website_url ?? "",
    linkedinUrl: profile.linkedin_url ?? "",
    contactPhone: profile.contact_phone ?? "",
    headquartersLocation: profile.headquarters_location ?? "",
    logoUrl: profile.logo_url ?? "",
  };
}

type FormState = ReturnType<typeof toFormState>;

export function IndustryProfileForm({
  profile,
  onCancel,
  onSaved,
}: {
  profile: IndustryProfile;
  onCancel: () => void;
  onSaved: (updated: IndustryProfile) => void;
}) {
  const [form, setForm] = useState<FormState>(() => toFormState(profile));
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const ids = {
    companyName: useId(),
    industrySector: useId(),
    companySize: useId(),
    foundedYear: useId(),
    companyDescription: useId(),
    websiteUrl: useId(),
    linkedinUrl: useId(),
    contactPhone: useId(),
    headquartersLocation: useId(),
    logoUrl: useId(),
  };

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const errors: FieldErrors = {};

    if (form.foundedYear.trim()) {
      const year = Number(form.foundedYear);
      if (!Number.isInteger(year) || year < 1800 || year > 2100) {
        errors.foundedYear = "Enter a year between 1800 and 2100.";
      }
    }
    if (form.contactPhone.trim() && !isValidPhone(form.contactPhone)) {
      errors.contactPhone = "7–20 characters: digits, spaces, +, -, or parentheses.";
    }
    if (form.websiteUrl.trim() && !isValidUrl(form.websiteUrl)) {
      errors.websiteUrl = "Enter a full URL starting with http:// or https://";
    }
    if (form.linkedinUrl.trim() && !isValidUrl(form.linkedinUrl)) {
      errors.linkedinUrl = "Enter a full URL starting with http:// or https://";
    }
    if (form.logoUrl.trim() && !isValidUrl(form.logoUrl)) {
      errors.logoUrl = "Enter a full image URL starting with http:// or https://";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    if (submitting || !validate()) return;
    setSubmitting(true);

    const fields: IndustryProfileFields = {
      company_name: form.companyName.trim() || null,
      industry_sector: form.industrySector.trim() || null,
      company_size: form.companySize,
      website_url: form.websiteUrl.trim() || null,
      company_description: form.companyDescription.trim() || null,
      headquarters_location: form.headquartersLocation.trim() || null,
      founded_year: form.foundedYear.trim() ? Number(form.foundedYear) : null,
      contact_phone: form.contactPhone.trim() || null,
      linkedin_url: form.linkedinUrl.trim() || null,
      logo_url: form.logoUrl.trim() || null,
    };

    try {
      const updated = await updateIndustryProfile(fields);
      onSaved(updated);
    } catch (err) {
      setFormError(
        err instanceof ApiError
          ? err.message
          : "Unable to save your company profile. Please try again.",
      );
      setSubmitting(false);
    }
  }

  const textareaClass =
    "w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30";

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">
      <FormError message={formError} />

      <Card>
        <CardHeader>
          <CardTitle>About Company</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={ids.companyName}>Company Name</Label>
            <Input
              id={ids.companyName}
              value={form.companyName}
              onChange={(e) => set("companyName", e.target.value)}
              maxLength={200}
              placeholder="e.g. Acme Robotics"
              disabled={submitting}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.industrySector}>Industry Sector</Label>
            <Input
              id={ids.industrySector}
              value={form.industrySector}
              onChange={(e) => set("industrySector", e.target.value)}
              maxLength={120}
              placeholder="e.g. Manufacturing"
              disabled={submitting}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.companySize}>Company Size</Label>
            <Select
              value={form.companySize ?? SIZE_UNSET}
              onValueChange={(value) =>
                set("companySize", value === SIZE_UNSET ? null : (value as CompanySize))
              }
              disabled={submitting}
            >
              <SelectTrigger id={ids.companySize} className="w-full">
                <SelectValue placeholder="Not specified" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={SIZE_UNSET}>Not specified</SelectItem>
                {COMPANY_SIZES.map((size) => (
                  <SelectItem key={size} value={size}>
                    {COMPANY_SIZE_LABELS[size]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.foundedYear}>Founded Year</Label>
            <Input
              id={ids.foundedYear}
              inputMode="numeric"
              value={form.foundedYear}
              onChange={(e) => set("foundedYear", e.target.value)}
              placeholder={`e.g. ${CURRENT_YEAR - 10}`}
              disabled={submitting}
              aria-invalid={!!fieldErrors.foundedYear}
            />
            <FieldError id={`${ids.foundedYear}-error`} message={fieldErrors.foundedYear} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor={ids.companyDescription}>Company Description</Label>
            <textarea
              id={ids.companyDescription}
              value={form.companyDescription}
              onChange={(e) => set("companyDescription", e.target.value)}
              rows={4}
              maxLength={5000}
              placeholder="What does your company do?"
              disabled={submitting}
              className={textareaClass}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Contact &amp; Presence</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
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
            <Label htmlFor={ids.linkedinUrl}>LinkedIn</Label>
            <Input
              id={ids.linkedinUrl}
              type="url"
              value={form.linkedinUrl}
              onChange={(e) => set("linkedinUrl", e.target.value)}
              placeholder="https://linkedin.com/company/..."
              disabled={submitting}
              aria-invalid={!!fieldErrors.linkedinUrl}
            />
            <FieldError id={`${ids.linkedinUrl}-error`} message={fieldErrors.linkedinUrl} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.contactPhone}>Phone</Label>
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
          <div className="space-y-1.5">
            <Label htmlFor={ids.headquartersLocation}>Headquarters</Label>
            <Input
              id={ids.headquartersLocation}
              value={form.headquartersLocation}
              onChange={(e) => set("headquartersLocation", e.target.value)}
              maxLength={200}
              placeholder="e.g. Pune, India"
              disabled={submitting}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Company Branding</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor={ids.logoUrl}>Logo URL</Label>
            <Input
              id={ids.logoUrl}
              type="url"
              value={form.logoUrl}
              onChange={(e) => set("logoUrl", e.target.value)}
              placeholder="https://.../logo.png"
              disabled={submitting}
              aria-invalid={!!fieldErrors.logoUrl}
            />
            <p className="text-xs text-muted-foreground">
              Paste an image link — direct file upload is coming later.
            </p>
            <FieldError id={`${ids.logoUrl}-error`} message={fieldErrors.logoUrl} />
          </div>
          {form.logoUrl.trim() && isValidUrl(form.logoUrl) ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={form.logoUrl}
              alt="Company logo preview"
              className="size-16 rounded-lg object-contain ring-1 ring-foreground/10"
            />
          ) : null}
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
