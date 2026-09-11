"use client";

import { useId, useState, useSyncExternalStore } from "react";
import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import {
  Building2,
  GraduationCap,
  Lock,
  Mail,
  School,
  ShieldCheck,
  Sparkles,
  Target,
} from "lucide-react";
import { toast } from "sonner";
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
import { cn } from "@/lib/utils";

interface FieldErrors {
  identifier?: string;
  password?: string;
}

const ROLE_HINTS = [
  {
    id: "student",
    label: "Student",
    icon: GraduationCap,
    accent: "text-indigo-600 dark:text-indigo-400",
    bg: "border-indigo-200 dark:border-indigo-800/60 bg-indigo-500/5",
    description: "Access verified assessments, skill badges, and explainable job matching.",
  },
  {
    id: "faculty",
    label: "Faculty",
    icon: Target,
    accent: "text-sky-600 dark:text-sky-400",
    bg: "border-sky-200 dark:border-sky-800/60 bg-sky-500/5",
    description: "Author questions, review assessment banks, and track student cohort analytics.",
  },
  {
    id: "industry",
    label: "Industry",
    icon: Building2,
    accent: "text-emerald-600 dark:text-emerald-400",
    bg: "border-emerald-200 dark:border-emerald-800/60 bg-emerald-500/5",
    description: "Post opportunities, review candidates ranked by match scores, and hire verified talent.",
  },
  {
    id: "institution",
    label: "Institution",
    icon: School,
    accent: "text-amber-600 dark:text-amber-400",
    bg: "border-amber-200 dark:border-amber-800/60 bg-amber-500/5",
    description: "Monitor campus placement metrics, department skill trends, and partner MoUs.",
  },
] as const;

const emptySubscribe = () => () => {};

export function LoginForm() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const identifierId = useId();
  const passwordId = useId();

  const [selectedRole, setSelectedRole] = useState<string>("student");
  const [identifier, setIdentifier] = useState("");
  const [password, setPassword] = useState("");
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [unverifiedEmail, setUnverifiedEmail] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [googleLoading, setGoogleLoading] = useState(false);
  const mounted = useSyncExternalStore(emptySubscribe, () => true, () => false);

  const oauthError = searchParams.get("error");
  const activeHint = ROLE_HINTS.find((r) => r.id === selectedRole) || ROLE_HINTS[0];

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
        const errorMsg = getAuthErrorMessage(error);
        if (errorMsg === "Please verify your email address before signing in.") {
          setUnverifiedEmail(true);
        }
        setFormError(errorMsg);
        toast.error("Sign-in failed", { description: errorMsg });
        setSubmitting(false);
        return;
      }

      if (!data.user) {
        const fallbackMsg = getAuthErrorMessage(null);
        setFormError(fallbackMsg);
        toast.error("Sign-in failed", { description: fallbackMsg });
        setSubmitting(false);
        return;
      }

      const role = await fetchProfileRole(supabase, data.user.id);
      const safeRedirect = getSafeRedirectPath(searchParams.get("redirectTo"));
      const destination = role ? (safeRedirect ?? getPostLoginRedirectPath(role)) : "/onboarding";

      toast.success("Welcome back!", {
        description: "Signing in and opening your workspace...",
      });

      window.location.assign(destination);
    } catch (err) {
      console.error("Login failed:", err);
      const errorMsg = getAuthErrorMessage(err);
      setFormError(errorMsg);
      toast.error("Sign-in failed", { description: errorMsg });
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
      // On success the browser navigates away to Google, so no further state change here.
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
      {/* Role Context Selector Pills */}
      <div className="space-y-2 rounded-xl border border-border/70 bg-muted/30 p-3">
        <div className="flex items-center justify-between px-0.5">
          <span className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
            Sign in to workspace:
          </span>
          <span className="flex items-center gap-1 text-[11px] font-medium text-primary">
            <Sparkles className="size-3" />
            Auto-routes on login
          </span>
        </div>
        <div className="grid grid-cols-4 gap-1.5">
          {ROLE_HINTS.map((hint) => {
            const Icon = hint.icon;
            const isSelected = selectedRole === hint.id;
            return (
              <button
                key={hint.id}
                type="button"
                onClick={() => setSelectedRole(hint.id)}
                className={cn(
                  "flex flex-col items-center justify-center gap-1 rounded-lg border py-2 px-1 text-center transition-all",
                  isSelected
                    ? "border-primary bg-background shadow-xs font-semibold text-foreground"
                    : "border-transparent bg-transparent text-muted-foreground hover:bg-background/50 hover:text-foreground",
                )}
              >
                <Icon className={cn("size-4", isSelected ? hint.accent : "text-muted-foreground")} />
                <span className="text-[11px] leading-tight">{hint.label}</span>
              </button>
            );
          })}
        </div>
        <div
          className={cn(
            "rounded-lg border px-3 py-2 text-xs transition-colors duration-200",
            activeHint.bg,
          )}
        >
          <span className={cn("font-medium", activeHint.accent)}>{activeHint.label} Portal: </span>
          <span className="text-muted-foreground">{activeHint.description}</span>
        </div>
      </div>

      {oauthError ? (
        <FormError message="We couldn't complete Google sign-in. Please try again." />
      ) : null}

      <FormError message={formError} />

      {unverifiedEmail ? (
        <div className="rounded-lg border border-amber-500/20 bg-amber-500/10 p-3 text-xs text-amber-700 dark:text-amber-400">
          Didn&apos;t receive the confirmation email?{" "}
          <Link href="/verify-email" className="font-semibold underline underline-offset-4 hover:opacity-80">
            Resend verification email
          </Link>
        </div>
      ) : null}

      <form
        method="POST"
        action="javascript:void(0)"
        onSubmit={handleSubmit}
        noValidate
        className="space-y-4"
      >
        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor={identifierId} className="flex items-center gap-1.5 text-xs font-medium">
              <Mail className="size-3.5 text-muted-foreground" />
              Username or Email
            </Label>
          </div>
          <Input
            id={identifierId}
            name="identifier"
            type="text"
            autoComplete="username"
            autoCapitalize="none"
            spellCheck={false}
            placeholder="e.g. alex.chen or alex@university.edu"
            value={identifier}
            onChange={(e) => setIdentifier(e.target.value)}
            aria-invalid={!!fieldErrors.identifier}
            aria-describedby={fieldErrors.identifier ? `${identifierId}-error` : undefined}
            disabled={submitting}
            className="h-10 transition-colors focus-visible:ring-2 focus-visible:ring-primary/20"
          />
          <FieldError id={`${identifierId}-error`} message={fieldErrors.identifier} />
        </div>

        <div className="space-y-1.5">
          <div className="flex items-center justify-between">
            <Label htmlFor={passwordId} className="flex items-center gap-1.5 text-xs font-medium">
              <Lock className="size-3.5 text-muted-foreground" />
              Password
            </Label>
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
            className="h-10 transition-colors focus-visible:ring-2 focus-visible:ring-primary/20"
          />
          <FieldError id={`${passwordId}-error`} message={fieldErrors.password} />
        </div>

        <div className="flex items-center justify-between pt-1">
          <label htmlFor="remember-device" className="flex cursor-pointer items-center gap-2 select-none">
            <input
              type="checkbox"
              id="remember-device"
              defaultChecked
              className="size-4 rounded border-border text-primary accent-primary focus:ring-primary/20"
            />
            <span className="text-xs text-muted-foreground">Keep me signed in</span>
          </label>
          <span className="text-[11px] text-muted-foreground">Session stays valid 30 days</span>
        </div>

        <Button
          type="submit"
          className="h-11 w-full bg-primary font-medium text-primary-foreground shadow-sm transition-all hover:bg-primary/90"
          disabled={submitting || !mounted}
        >
          {submitting ? "Signing in to workspace..." : !mounted ? "Loading portal..." : "Sign In to Portal"}
        </Button>
      </form>

      <div className="flex items-center gap-3" aria-hidden="true">
        <div className="h-px flex-1 bg-border/80" />
        <span className="text-xs font-medium text-muted-foreground">OR CONTINUE WITH</span>
        <div className="h-px flex-1 bg-border/80" />
      </div>

      <GoogleButton onClick={handleGoogleSignIn} loading={googleLoading} disabled={submitting} />

      <div className="flex items-center justify-center gap-1.5 rounded-lg border border-border/50 bg-muted/20 py-2 px-3 text-[11px] text-muted-foreground">
        <ShieldCheck className="size-3.5 text-emerald-600 dark:text-emerald-400" />
        <span>Strict Row-Level Security · 256-bit Encrypted Session</span>
      </div>

      <p className="text-center text-sm text-muted-foreground">
        Don&apos;t have an account?{" "}
        <Link href="/register" className="font-semibold text-primary underline-offset-4 hover:underline">
          Create account
        </Link>
      </p>
    </div>
  );
}
