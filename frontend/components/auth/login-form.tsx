"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/auth/password-input";
import { GoogleButton } from "@/components/auth/google-button";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { createClient } from "@/lib/supabase/client";
import {
  fetchProfileRole,
  getAuthErrorMessage,
  getPostLoginRedirectPath,
  getSafeRedirectPath,
  signInWithGoogle,
  signInWithIdentifier,
} from "@/lib/auth";
import { isValidIdentifier } from "@/lib/validations";

interface FieldErrors {
  identifier?: string;
  password?: string;
}

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const identifierId = useId();
  const passwordId = useId();

  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [unverifiedEmail, setUnverifiedEmail] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  const oauthError = searchParams.get("error");

  function validate(): boolean {
    const errors: FieldErrors = {};

    if (!identifier.trim()) {
      errors.identifier = "Please enter your username or email.";
    } else if (!isValidIdentifier(identifier)) {
      errors.identifier = "Please enter a valid email or username.";
    }

    if (!password) {
      errors.password = "Please enter your password.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setUnverifiedEmail(false);

    if (submitting || !validate()) return;

    setSubmitting(true);

    try {
      const supabase = createClient();
      const { data, error } = await signInWithIdentifier(supabase, identifier, password);

      if (error) {
        if (getAuthErrorMessage(error) === "Please verify your email address before signing in.") {
          setUnverifiedEmail(true);
        }
        setFormError(getAuthErrorMessage(error));
        setSubmitting(false);
        return;
      }

      if (!data.user) {
        setFormError(getAuthErrorMessage(null));
        setSubmitting(false);
        return;
      }

      const role = await fetchProfileRole(supabase, data.user.id);
      const safeRedirect = getSafeRedirectPath(searchParams.get("redirectTo"));
      const destination = role ? (safeRedirect ?? getPostLoginRedirectPath(role)) : "/onboarding";

      router.push(destination);
      router.refresh();
    } catch (err) {
      console.error("Login failed:", err);
      setFormError(getAuthErrorMessage(err));
      setSubmitting(false);
    }
  }

  async function handleGoogleSignIn() {
    setFormError(null);
    setGoogleLoading(true);

    try {
      const supabase = createClient();
      const { error } = await signInWithGoogle(supabase, `${window.location.origin}/auth/callback`);

      if (error) {
        setFormError(getAuthErrorMessage(error));
        setGoogleLoading(false);
      }
      // On success the browser navigates away to Google, so no further state change here.
    } catch (err) {
      console.error("Google sign-in failed:", err);
      setFormError(getAuthErrorMessage(err));
      setGoogleLoading(false);
    }
  }

  return (
    <div className="space-y-5">
      {oauthError ? (
        <FormError message="We couldn't complete Google sign-in. Please try again." />
      ) : null}

      <FormError message={formError} />

      {unverifiedEmail ? (
        <p className="text-xs text-muted-foreground">
          Didn&apos;t get the email?{" "}
          <Link href="/verify-email" className="font-medium text-primary underline-offset-4 hover:underline">
            Resend verification
          </Link>
        </p>
      ) : null}

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor={identifierId}>Username or Email</Label>
          <Input
            id={identifierId}
            name="identifier"
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            aria-invalid={!!fieldErrors.identifier}
            aria-describedby={fieldErrors.identifier ? `${identifierId}-error` : undefined}
            disabled={submitting}
            className="h-10"
          />
          <FieldError id={`${identifierId}-error`} message={fieldErrors.identifier} />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor={passwordId}>Password</Label>
            <Link
              href="/forgot-password"
              className="text-xs font-medium text-primary underline-offset-4 hover:underline"
            >
              Forgot password?
            </Link>
          </div>
          <PasswordInput
            id={passwordId}
            name="password"
            autoComplete="current-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={!!fieldErrors.password}
            aria-describedby={fieldErrors.password ? `${passwordId}-error` : undefined}
            disabled={submitting}
          />
          <FieldError id={`${passwordId}-error`} message={fieldErrors.password} />
        </div>

        <Button type="submit" className="h-10 w-full" disabled={submitting}>
          {submitting ? "Signing in..." : "Sign In"}
        </Button>
      </form>

      <div className="flex items-center gap-3" aria-hidden="true">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground">OR</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <GoogleButton onClick={handleGoogleSignIn} loading={googleLoading} disabled={submitting} />

      <p className="text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{" "}
        <Link href="/register" className="font-medium text-primary underline-offset-4 hover:underline">
          Create account
        </Link>
      </p>
    </div>
  );
}
