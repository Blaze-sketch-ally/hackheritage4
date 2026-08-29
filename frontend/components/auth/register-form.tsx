"use client";

import { useId, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { PasswordInput } from "@/components/auth/password-input";
import { PasswordStrength } from "@/components/auth/password-strength";
import { GoogleButton } from "@/components/auth/google-button";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { createClient } from "@/lib/supabase/client";
import {
  fetchProfileRole,
  getAuthErrorMessage,
  getPostLoginRedirectPath,
  resolveIdentifierToEmail,
  signInWithGoogle,
  signUpWithEmail,
  syncProfileUsernameFromMetadata,
} from "@/lib/auth";
import { isPasswordValid, isValidEmail, isValidFullName, isValidUsername } from "@/lib/validations";

interface FieldErrors {
  fullName?: string;
  username?: string;
  email?: string;
  password?: string;
  confirmPassword?: string;
}

export function RegisterForm() {
  const router = useRouter();
  const fullNameId = useId();
  const usernameId = useId();
  const emailId = useId();
  const passwordId = useId();
  const confirmPasswordId = useId();

  const [fullName, setFullName] = useState("");
  const [username, setUsername] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);

  function validate(): boolean {
    const errors: FieldErrors = {};

    if (!fullName.trim()) {
      errors.fullName = "Please enter your full name.";
    } else if (!isValidFullName(fullName)) {
      errors.fullName = "Please enter your full name.";
    }

    if (!username.trim()) {
      errors.username = "Please choose a username.";
    } else if (!isValidUsername(username)) {
      errors.username = "3-30 characters: letters, numbers, underscore, dot, or dash.";
    }

    if (!email.trim()) {
      errors.email = "Please enter your email address.";
    } else if (!isValidEmail(email)) {
      errors.email = "Please enter a valid email address.";
    }

    if (!password) {
      errors.password = "Please enter a password.";
    } else if (!isPasswordValid(password)) {
      errors.password = "Password does not meet the requirements below.";
    }

    if (!confirmPassword) {
      errors.confirmPassword = "Please confirm your password.";
    } else if (confirmPassword !== password) {
      errors.confirmPassword = "Passwords do not match.";
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);

    if (submitting || !validate()) return;

    setSubmitting(true);

    try {
      const supabase = createClient();
      const trimmedUsername = username.trim();
      const trimmedEmail = email.trim();
      const trimmedFullName = fullName.trim();

      // Reuses the same identifier-resolution RPC the login form uses for
      // username lookups — a non-null result means the username is taken.
      const existingEmail = await resolveIdentifierToEmail(supabase, trimmedUsername);
      if (existingEmail) {
        setFieldErrors((prev) => ({ ...prev, username: "That username is already taken." }));
        setSubmitting(false);
        return;
      }

      const { data, error } = await signUpWithEmail(supabase, {
        email: trimmedEmail,
        password,
        fullName: trimmedFullName,
        username: trimmedUsername,
        emailRedirectTo: `${window.location.origin}/auth/callback`,
      });

      if (error) {
        setFormError(getAuthErrorMessage(error));
        setSubmitting(false);
        return;
      }

      if (!data.user) {
        setFormError(getAuthErrorMessage(null));
        setSubmitting(false);
        return;
      }

      if (!data.session) {
        // Email confirmation is required — no session yet. Reuse the
        // existing verify-email page rather than building a second one;
        // this also covers Supabase's anti-enumeration "obfuscated user"
        // response for an already-registered email, which looks identical
        // to a genuine new signup here.
        router.push(`/verify-email?email=${encodeURIComponent(trimmedEmail)}`);
        return;
      }

      // Email confirmation is disabled — Supabase returned a session
      // immediately, so this is already an authenticated sign-in.
      await syncProfileUsernameFromMetadata(supabase, data.user.id, data.user.user_metadata);
      const role = await fetchProfileRole(supabase, data.user.id);
      router.push(role ? getPostLoginRedirectPath(role) : "/onboarding");
      router.refresh();
    } catch (err) {
      console.error("Registration failed:", err);
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
      <FormError message={formError} />

      <form onSubmit={handleSubmit} noValidate className="space-y-4">
        <div className="space-y-1.5">
          <Label htmlFor={fullNameId}>Full Name</Label>
          <Input
            id={fullNameId}
            name="name"
            type="text"
            autoComplete="name"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            aria-invalid={!!fieldErrors.fullName}
            aria-describedby={fieldErrors.fullName ? `${fullNameId}-error` : undefined}
            disabled={submitting}
            className="h-10"
          />
          <FieldError id={`${fullNameId}-error`} message={fieldErrors.fullName} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={usernameId}>Username</Label>
          <Input
            id={usernameId}
            name="username"
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            aria-invalid={!!fieldErrors.username}
            aria-describedby={fieldErrors.username ? `${usernameId}-error` : undefined}
            disabled={submitting}
            className="h-10"
          />
          <FieldError id={`${usernameId}-error`} message={fieldErrors.username} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={emailId}>Email</Label>
          <Input
            id={emailId}
            name="email"
            type="email"
            autoComplete="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={!!fieldErrors.email}
            aria-describedby={fieldErrors.email ? `${emailId}-error` : undefined}
            disabled={submitting}
            className="h-10"
          />
          <FieldError id={`${emailId}-error`} message={fieldErrors.email} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={passwordId}>Password</Label>
          <PasswordInput
            id={passwordId}
            name="new-password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={!!fieldErrors.password}
            aria-describedby={`${passwordId}-strength${fieldErrors.password ? ` ${passwordId}-error` : ""}`}
            disabled={submitting}
          />
          <FieldError id={`${passwordId}-error`} message={fieldErrors.password} />
          <div id={`${passwordId}-strength`}>
            <PasswordStrength password={password} />
          </div>
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={confirmPasswordId}>Confirm Password</Label>
          <PasswordInput
            id={confirmPasswordId}
            name="confirm-password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            aria-invalid={!!fieldErrors.confirmPassword}
            aria-describedby={fieldErrors.confirmPassword ? `${confirmPasswordId}-error` : undefined}
            disabled={submitting}
          />
          <FieldError id={`${confirmPasswordId}-error`} message={fieldErrors.confirmPassword} />
        </div>

        <Button type="submit" className="h-10 w-full" disabled={submitting}>
          {submitting ? "Creating account..." : "Create Account"}
        </Button>
      </form>

      <div className="flex items-center gap-3" aria-hidden="true">
        <div className="h-px flex-1 bg-border" />
        <span className="text-xs text-muted-foreground">OR</span>
        <div className="h-px flex-1 bg-border" />
      </div>

      <GoogleButton onClick={handleGoogleSignIn} loading={googleLoading} disabled={submitting} />

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-medium text-primary underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
