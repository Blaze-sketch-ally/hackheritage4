"use client";

import { useEffect, useId, useState } from "react";
import { useRouter } from "next/navigation";
import { CheckCircle2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/auth/password-input";
import { PasswordStrength } from "@/components/auth/password-strength";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { createClient } from "@/lib/supabase/client";
import { getAuthErrorMessage, updatePassword } from "@/lib/auth";
import { isPasswordValid } from "@/lib/validations";

type Status = "checking" | "invalid" | "form" | "success";

export function ResetPasswordForm() {
  const router = useRouter();
  const newPasswordId = useId();
  const confirmPasswordId = useId();

  const [status, setStatus] = useState<Status>("checking");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [newPasswordError, setNewPasswordError] = useState<string | undefined>();
  const [confirmPasswordError, setConfirmPasswordError] = useState<string | undefined>();
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  // A valid recovery session only exists once /auth/callback has exchanged
  // the email link's code for a session — opening this page directly, or
  // with an expired/already-used link, means no session is present.
  useEffect(() => {
    let unsubscribe: (() => void) | undefined;

    async function check() {
      try {
        const supabase = createClient();
        const {
          data: { session },
        } = await supabase.auth.getSession();
        setStatus(session ? "form" : "invalid");

        const {
          data: { subscription },
        } = supabase.auth.onAuthStateChange((event, changedSession) => {
          if (event === "PASSWORD_RECOVERY" || changedSession) {
            setStatus("form");
          }
        });
        unsubscribe = () => subscription.unsubscribe();
      } catch (err) {
        console.error("Recovery session check failed:", err);
        setStatus("invalid");
      }
    }

    check();

    return () => unsubscribe?.();
  }, []);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

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

      setStatus("success");
    } catch (err) {
      console.error("Password update failed:", err);
      setSubmitting(false);
      setFormError(getAuthErrorMessage(err));
    }
  }

  async function handleContinueToLogin() {
    // End the recovery session so the user signs back in with the new password.
    try {
      await createClient().auth.signOut();
    } catch (err) {
      console.error("Sign-out before login redirect failed:", err);
    }
    router.push("/login");
  }

  if (status === "checking") {
    return <p className="text-center text-sm text-muted-foreground">Checking your reset link...</p>;
  }

  if (status === "invalid") {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <p className="text-sm text-muted-foreground">
          Your password reset link is invalid or has expired.
        </p>
        <Button type="button" className="h-10 w-full" onClick={() => router.push("/forgot-password")}>
          Request a new reset link
        </Button>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="flex flex-col items-center gap-4 text-center">
        <CheckCircle2 className="size-10 text-green-600" aria-hidden="true" />
        <div className="space-y-1">
          <p className="text-sm font-medium">Password reset successfully</p>
          <p className="text-sm text-muted-foreground">
            Your password has been updated. You can now sign in with your new password.
          </p>
        </div>
        <Button type="button" className="h-10 w-full" onClick={handleContinueToLogin}>
          Continue to Login
        </Button>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <p className="text-sm text-muted-foreground">Create a new password for your account.</p>

      <FormError message={formError} />

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

      <Button
        type="submit"
        className="h-10 w-full"
        disabled={submitting || !isPasswordValid(newPassword) || confirmPassword !== newPassword}
      >
        {submitting ? "Resetting password..." : "Reset Password"}
      </Button>
    </form>
  );
}
