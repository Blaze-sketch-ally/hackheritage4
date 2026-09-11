"use client";

import { useId, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import {
  AtSign,
  CheckCircle2,
  Lock,
  Mail,
  ShieldCheck,
  Sparkles,
  User,
} from "lucide-react";
import { toast } from "sonner";
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

const emptySubscribe = () => () => {};

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
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false);

  // Real-time helper validation indicators
  const isUsernameFormatValid = username.length >= 3 && isValidUsername(username);
  const isEmailFormatValid = email.length > 3 && isValidEmail(email);
  const doPasswordsMatch = Boolean(password && confirmPassword && password === confirmPassword);

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
        const errorMsg = getAuthErrorMessage(error);
        setFormError(errorMsg);
        toast.error("Registration failed", { description: errorMsg });
        setSubmitting(false);
        return;
      }

      if (!data.user) {
        const fallbackMsg = getAuthErrorMessage(null);
        setFormError(fallbackMsg);
        toast.error("Registration failed", { description: fallbackMsg });
        setSubmitting(false);
        return;
      }

      if (!data.session) {
        toast.info("Verification email sent!", {
          description: "Please check your inbox to confirm your email and proceed.",
        });
        router.push(`/verify-email?email=${encodeURIComponent(trimmedEmail)}`);
        return;
      }

      toast.success("Account created successfully!", {
        description: "Setting up your workspace profile...",
      });

      await syncProfileUsernameFromMetadata(supabase, data.user.id, data.user.user_metadata);
      const role = await fetchProfileRole(supabase, data.user.id);
      const destination = role ? getPostLoginRedirectPath(role) : "/onboarding";
      window.location.assign(destination);
    } catch (err) {
      console.error("Registration failed:", err);
      const errorMsg = getAuthErrorMessage(err);
      setFormError(errorMsg);
      toast.error("Registration failed", { description: errorMsg });
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
        const errorMsg = getAuthErrorMessage(error);
        setFormError(errorMsg);
        toast.error("Google sign-in failed", { description: errorMsg });
        setGoogleLoading(false);
      }
    } catch (err) {
      console.error("Google sign-in failed:", err);
      const errorMsg = getAuthErrorMessage(err);
      setFormError(errorMsg);
      toast.error("Google sign-in failed", { description: errorMsg });
      setGoogleLoading(false);
    }
  }

  return (
    <div className="space-y-6">
      {/* 2-Step Onboarding Indicator */}
      <div className="rounded-xl border border-border/70 bg-muted/30 p-3.5">
        <div className="flex items-center justify-between text-xs font-semibold">
          <span className="flex items-center gap-1.5 text-primary">
            <span className="flex size-5 items-center justify-center rounded-full bg-primary text-[11px] text-primary-foreground font-bold">
              1
            </span>
            Account Credentials
          </span>
          <span className="flex items-center gap-1 text-muted-foreground font-normal">
            <Sparkles className="size-3.5 text-primary" />
            Step 2: Choose Workspace Role
          </span>
        </div>
        <p className="mt-2 text-xs text-muted-foreground leading-relaxed">
          Create your portal login below. In the next step, you will select your primary role:{" "}
          <strong className="text-foreground font-medium">Student</strong>,{" "}
          <strong className="text-foreground font-medium">Faculty</strong>,{" "}
          <strong className="text-foreground font-medium">Recruiter</strong>, or{" "}
          <strong className="text-foreground font-medium">Institution Admin</strong>.
        </p>
      </div>

      <FormError message={formError} />

      <form
        method="POST"
        action="javascript:void(0)"
        onSubmit={handleSubmit}
        noValidate
        className="space-y-4"
      >
        <div className="space-y-1.5">
          <Label htmlFor={fullNameId} className="flex items-center gap-1.5 text-xs font-medium">
            <User className="size-3.5 text-muted-foreground" />
            Full Name
          </Label>
          <Input
            id={fullNameId}
            name="name"
            type="text"
            autoComplete="name"
            placeholder="e.g. Alexandra Chen"
            value={fullName}
            onChange={(e) => setFullName(e.target.value)}
            aria-invalid={!!fieldErrors.fullName}
            aria-describedby={fieldErrors.fullName ? `${fullNameId}-error` : undefined}
            disabled={submitting}
            className="h-10 transition-colors focus-visible:ring-2 focus-visible:ring-primary/20"
          />
          <FieldError id={`${fullNameId}-error`} message={fieldErrors.fullName} />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor={usernameId} className="flex items-center gap-1.5 text-xs font-medium">
              <AtSign className="size-3.5 text-muted-foreground" />
              Username
            </Label>
            {isUsernameFormatValid && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="size-3" /> Valid format
              </span>
            )}
          </div>
          <Input
            id={usernameId}
            name="username"
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="e.g. alex.chen"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            aria-invalid={!!fieldErrors.username}
            aria-describedby={fieldErrors.username ? `${usernameId}-error` : undefined}
            disabled={submitting}
            className="h-10 transition-colors focus-visible:ring-2 focus-visible:ring-primary/20"
          />
          <FieldError id={`${usernameId}-error`} message={fieldErrors.username} />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor={emailId} className="flex items-center gap-1.5 text-xs font-medium">
              <Mail className="size-3.5 text-muted-foreground" />
              Email Address
            </Label>
            {isEmailFormatValid && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="size-3" /> Valid email
              </span>
            )}
          </div>
          <Input
            id={emailId}
            name="email"
            type="email"
            autoComplete="email"
            placeholder="alex@university.edu"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            aria-invalid={!!fieldErrors.email}
            aria-describedby={fieldErrors.email ? `${emailId}-error` : undefined}
            disabled={submitting}
            className="h-10 transition-colors focus-visible:ring-2 focus-visible:ring-primary/20"
          />
          <FieldError id={`${emailId}-error`} message={fieldErrors.email} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={passwordId} className="flex items-center gap-1.5 text-xs font-medium">
            <Lock className="size-3.5 text-muted-foreground" />
            Password
          </Label>
          <PasswordInput
            id={passwordId}
            name="new-password"
            autoComplete="new-password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            aria-invalid={!!fieldErrors.password}
            aria-describedby={`${passwordId}-strength${fieldErrors.password ? ` ${passwordId}-error` : ""}`}
            disabled={submitting}
            className="h-10 transition-colors focus-visible:ring-2 focus-visible:ring-primary/20"
          />
          <FieldError id={`${passwordId}-error`} message={fieldErrors.password} />
          <div id={`${passwordId}-strength`}>
            <PasswordStrength password={password} />
          </div>
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor={confirmPasswordId} className="flex items-center gap-1.5 text-xs font-medium">
              <Lock className="size-3.5 text-muted-foreground" />
              Confirm Password
            </Label>
            {doPasswordsMatch && (
              <span className="flex items-center gap-1 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                <CheckCircle2 className="size-3" /> Passwords match
              </span>
            )}
          </div>
          <PasswordInput
            id={confirmPasswordId}
            name="confirm-password"
            autoComplete="new-password"
            value={confirmPassword}
            onChange={(e) => setConfirmPassword(e.target.value)}
            aria-invalid={!!fieldErrors.confirmPassword}
            aria-describedby={fieldErrors.confirmPassword ? `${confirmPasswordId}-error` : undefined}
            disabled={submitting}
            className="h-10 transition-colors focus-visible:ring-2 focus-visible:ring-primary/20"
          />
          <FieldError id={`${confirmPasswordId}-error`} message={fieldErrors.confirmPassword} />
        </div>

        <p className="text-[11px] leading-normal text-muted-foreground">
          By selecting Create Account, you acknowledge that you agree to the portal{" "}
          <span className="text-foreground underline underline-offset-2">Terms of Service</span> and{" "}
          <span className="text-foreground underline underline-offset-2">Data Privacy Policy</span>.
        </p>

        <Button
          type="submit"
          className="h-11 w-full bg-primary font-medium text-primary-foreground shadow-sm transition-all hover:bg-primary/90"
          disabled={submitting || !mounted}
        >
          {submitting ? "Creating account..." : !mounted ? "Loading portal..." : "Create Account & Continue"}
        </Button>
      </form>

      <div className="flex items-center gap-3" aria-hidden="true">
        <div className="h-px flex-1 bg-border/80" />
        <span className="text-xs font-medium text-muted-foreground">OR SIGN UP WITH</span>
        <div className="h-px flex-1 bg-border/80" />
      </div>

      <GoogleButton onClick={handleGoogleSignIn} loading={googleLoading} disabled={submitting} />

      <div className="flex items-center justify-center gap-1.5 rounded-lg border border-border/50 bg-muted/20 py-2 px-3 text-[11px] text-muted-foreground">
        <ShieldCheck className="size-3.5 text-emerald-600 dark:text-emerald-400" />
        <span>Enterprise Data Protection · Row-Level Multi-Tenant Security</span>
      </div>

      <p className="text-center text-sm text-muted-foreground">
        Already have an account?{" "}
        <Link href="/login" className="font-semibold text-primary underline-offset-4 hover:underline">
          Sign in
        </Link>
      </p>
    </div>
  );
}
