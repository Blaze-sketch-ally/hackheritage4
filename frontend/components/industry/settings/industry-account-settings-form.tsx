"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { createClient } from "@/lib/supabase/client";
import { getAuthErrorMessage } from "@/lib/auth";
import { updateProfile } from "@/lib/profile";
import { isValidFullName, isValidUrl, isValidUsername } from "@/lib/validations";
import type { Profile } from "@/types/user";

/**
 * The Account section of Industry Settings -- edits only the base
 * `profiles` identity fields (full_name/username/avatar_url) via the
 * existing updateProfile() (lib/profile.ts), the same mechanism and
 * validation already proven by components/student/profile/
 * student-profile-form.tsx. Company/organization fields
 * (industry_profiles) are deliberately out of scope here -- they remain
 * on /industry/profile. email and role are never read from or written by
 * this form.
 */

interface FieldErrors {
  fullName?: string;
  username?: string;
  avatarUrl?: string;
}

function toFormState(profile: Profile) {
  return {
    fullName: profile.full_name ?? "",
    username: profile.username ?? "",
    avatarUrl: profile.avatar_url ?? "",
  };
}

type FormState = ReturnType<typeof toFormState>;

export function IndustryAccountSettingsForm({
  profile,
  onSaved,
}: {
  profile: Profile;
  onSaved: (updated: Profile) => void;
}) {
  const [form, setForm] = useState<FormState>(() => toFormState(profile));
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const ids = { fullName: useId(), username: useId(), avatarUrl: useId() };

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const errors: FieldErrors = {};
    if (!form.fullName.trim() || !isValidFullName(form.fullName)) {
      errors.fullName = "Please enter your full name.";
    }
    if (!form.username.trim() || !isValidUsername(form.username)) {
      errors.username = "3-30 characters: letters, numbers, underscore, dot, or dash.";
    }
    if (form.avatarUrl.trim() && !isValidUrl(form.avatarUrl)) {
      errors.avatarUrl = "Please enter a valid URL.";
    }
    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setFormSuccess(null);
    if (submitting || !validate()) return;
    setSubmitting(true);

    try {
      const supabase = createClient();
      const { data, error } = await updateProfile(supabase, profile.id, {
        full_name: form.fullName.trim(),
        username: form.username.trim(),
        avatar_url: form.avatarUrl.trim() || null,
      });

      if (error) {
        setFormError(getAuthErrorMessage(error));
        setSubmitting(false);
        return;
      }

      setSubmitting(false);
      setFormSuccess("Account settings saved.");
      if (data) onSaved(data as Profile);
    } catch (err) {
      console.error("Account settings update failed:", err);
      setSubmitting(false);
      setFormError(getAuthErrorMessage(err));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Account</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <FormError message={formError} />
          <FormSuccess message={formSuccess} />

          <div className="space-y-1.5">
            <Label htmlFor={ids.fullName}>Full Name</Label>
            <Input
              id={ids.fullName}
              value={form.fullName}
              onChange={(e) => set("fullName", e.target.value)}
              disabled={submitting}
              aria-invalid={!!fieldErrors.fullName}
            />
            <FieldError id={`${ids.fullName}-error`} message={fieldErrors.fullName} />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor={ids.username}>Username</Label>
            <Input
              id={ids.username}
              value={form.username}
              onChange={(e) => set("username", e.target.value)}
              autoCapitalize="none"
              spellCheck={false}
              disabled={submitting}
              aria-invalid={!!fieldErrors.username}
            />
            <FieldError id={`${ids.username}-error`} message={fieldErrors.username} />
          </div>

          <div className="space-y-1.5">
            <Label htmlFor={ids.avatarUrl}>Avatar URL</Label>
            <Input
              id={ids.avatarUrl}
              value={form.avatarUrl}
              onChange={(e) => set("avatarUrl", e.target.value)}
              placeholder="https://..."
              disabled={submitting}
              aria-invalid={!!fieldErrors.avatarUrl}
            />
            <p className="text-xs text-muted-foreground">
              Paste an image link — file upload is coming later.
            </p>
            <FieldError id={`${ids.avatarUrl}-error`} message={fieldErrors.avatarUrl} />
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving..." : "Save Changes"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
