"use client";

import { useId, useState } from "react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/auth/password-input";
import { PasswordStrength } from "@/components/auth/password-strength";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { createClient } from "@/lib/supabase/client";
import { getAuthErrorMessage, updatePassword } from "@/lib/auth";
import { isPasswordValid } from "@/lib/validations";

/**
 * The Security section of Industry Settings -- reuses updatePassword()
 * (lib/auth.ts, supabase.auth.updateUser({ password })) exactly as
 * components/auth/reset-password-form.tsx does, but for the currently
 * authenticated session rather than a recovery session. Supabase's
 * updateUser() re-authenticates using the caller's existing valid
 * session -- it does not require re-entering the current password, so
 * this form doesn't ask for one, matching the existing infrastructure's
 * own behavior rather than inventing an extra step.
 */
export function ChangePasswordForm() {
  const newPasswordId = useId();
  const confirmPasswordId = useId();

  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [newPasswordError, setNewPasswordError] = useState<string | undefined>();
  const [confirmPasswordError, setConfirmPasswordError] = useState<string | undefined>();
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setFormSuccess(null);

    let hasError = false;
    if (!isPasswordValid(newPassword)) {
      setNewPasswordError("Password does not meet the requirements below.");
      hasError = true;
    } else {
      setNewPasswordError(undefined);
    }
    if (confirmPassword !== newPassword) {
      setConfirmPasswordError("Passwords do not match.");
      hasError = true;
    } else {
      setConfirmPasswordError(undefined);
    }

    if (hasError || submitting) return;
    setSubmitting(true);

    try {
      const { error } = await updatePassword(createClient(), newPassword);
      setSubmitting(false);

      if (error) {
        setFormError(getAuthErrorMessage(error));
        return;
      }

      setNewPassword("");
      setConfirmPassword("");
      setFormSuccess("Password updated successfully.");
    } catch (err) {
      console.error("Password update failed:", err);
      setSubmitting(false);
      setFormError(getAuthErrorMessage(err));
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Security</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <FormError message={formError} />
          <FormSuccess message={formSuccess} />

          <div className="space-y-1.5">
            <Label htmlFor={newPasswordId}>New Password</Label>
            <PasswordInput
              id={newPasswordId}
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              aria-invalid={!!newPasswordError}
              aria-describedby={`${newPasswordId}-strength${newPasswordError ? ` ${newPasswordId}-error` : ""}`}
              disabled={submitting}
            />
            <FieldError id={`${newPasswordId}-error`} message={newPasswordError} />
            <div id={`${newPasswordId}-strength`}>
              <PasswordStrength password={newPassword} />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor={confirmPasswordId}>Confirm New Password</Label>
            <PasswordInput
              id={confirmPasswordId}
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              aria-invalid={!!confirmPasswordError}
              aria-describedby={confirmPasswordError ? `${confirmPasswordId}-error` : undefined}
              disabled={submitting}
            />
            <FieldError id={`${confirmPasswordId}-error`} message={confirmPasswordError} />
          </div>

          <div className="flex justify-end">
            <Button type="submit" disabled={submitting}>
              {submitting ? "Updating..." : "Change Password"}
            </Button>
          </div>
        </form>
      </CardContent>
    </Card>
  );
}
