"use client";

import { useId, useState } from "react";
import { MailCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { createClient } from "@/lib/supabase/client";
import { getAuthErrorMessage, sendPasswordRecoveryEmail } from "@/lib/auth";
import { isValidEmail } from "@/lib/validations";

export function ForgotPasswordForm() {
  const emailId = useId();
  const [email, setEmail] = useState("");
  const [fieldError, setFieldError] = useState<string | undefined>();
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [sent, setSent] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    const trimmed = email.trim();
    if (!trimmed) {
      setFieldError("Please enter your email address.");
      return;
    }
    if (!isValidEmail(trimmed)) {
      setFieldError("Please enter a valid email address.");
      return;
    }
    setFieldError(undefined);

    setSubmitting(true);

    try {
      const redirectTo = `${window.location.origin}/auth/callback?next=/reset-password`;
      const { error } = await sendPasswordRecoveryEmail(createClient(), trimmed, redirectTo);
      setSubmitting(false);

      if (error) {
        setFormError(getAuthErrorMessage(error));
        return;
      }

      setSent(true);
    } catch (err) {
      console.error("Send password reset link failed:", err);
      setSubmitting(false);
      setFormError(getAuthErrorMessage(err));
    }
  }

  if (sent) {
    return (
      <div className="flex flex-col items-center gap-3 text-center">
        <MailCheck className="size-10 text-primary" aria-hidden="true" />
        <p className="text-sm font-medium">Check your email</p>
        <p className="text-sm text-muted-foreground">
          We&apos;ve sent a password reset link if an account exists for this email.
        </p>
      </div>
    );
  }

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <p className="text-sm text-muted-foreground">
        Enter your email address and we&apos;ll send you a password reset link.
      </p>

      <FormError message={formError} />

      <div className="space-y-1.5">
        <Label htmlFor={emailId}>Enter your email</Label>
        <Input
          id={emailId}
          type="email"
          autoComplete="email"
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          aria-invalid={!!fieldError}
          aria-describedby={fieldError ? `${emailId}-error` : undefined}
          disabled={submitting}
          className="h-10"
        />
        <FieldError id={`${emailId}-error`} message={fieldError} />
      </div>

      <Button type="submit" className="h-10 w-full" disabled={submitting}>
        {submitting ? "Sending link..." : "Send Reset Link"}
      </Button>
    </form>
  );
}
