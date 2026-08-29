import type { SupabaseClient } from "@supabase/supabase-js";
import type { PublicRole, UserRole } from "@/lib/constants";

/**
 * Resolves a login identifier (email or username) to the email Supabase
 * Auth needs. Usernames are resolved through a SECURITY DEFINER Postgres
 * function (see database/migrations/001_profiles.sql) so the frontend
 * never needs direct read access to other users' emails and never uses
 * the service role key.
 */
export async function resolveIdentifierToEmail(
  supabase: SupabaseClient,
  identifier: string,
): Promise<string | null> {
  const trimmed = identifier.trim();
  if (trimmed.includes("@")) return trimmed;

  const { data, error } = await supabase.rpc("get_email_for_identifier", {
    identifier: trimmed,
  });

  if (error) return null;
  return (data as string | null) ?? null;
}

/**
 * Signs in with an email OR username + password. Resolution failures are
 * reported with the same error shape as a wrong password so a missing
 * username can't be distinguished from an incorrect one.
 */
export async function signInWithIdentifier(
  supabase: SupabaseClient,
  identifier: string,
  password: string,
) {
  const email = await resolveIdentifierToEmail(supabase, identifier);

  if (!email) {
    return { data: { user: null, session: null }, error: { message: "Invalid login credentials" } };
  }

  return supabase.auth.signInWithPassword({ email, password });
}

export async function signInWithGoogle(supabase: SupabaseClient, redirectTo: string) {
  return supabase.auth.signInWithOAuth({
    provider: "google",
    options: {
      redirectTo,
      // Force the account chooser every time, even when Chrome already has
      // an active Google session — otherwise Google silently signs the user
      // into whichever account is currently active.
      queryParams: { prompt: "select_account" },
    },
  });
}

/** Maps a role to where a signed-in user should land. Null/missing role -> onboarding. */
export function getPostLoginRedirectPath(role: UserRole | null | undefined): string {
  switch (role) {
    case "STUDENT":
      return "/student/dashboard";
    case "FACULTY":
      return "/faculty/dashboard";
    case "INDUSTRY":
      return "/industry/dashboard";
    case "INSTITUTION":
      return "/institution/dashboard";
    case "ADMIN":
      return "/admin/dashboard";
    default:
      return "/onboarding";
  }
}

/** Only accepts an internal path (guards against open-redirect via `redirectTo`). */
export function getSafeRedirectPath(path: string | null | undefined): string | null {
  if (!path) return null;
  if (!path.startsWith("/") || path.startsWith("//")) return null;
  return path;
}

export async function fetchProfileRole(
  supabase: SupabaseClient,
  userId: string,
): Promise<UserRole | null> {
  const { data } = await supabase
    .from("profiles")
    .select("role")
    .eq("id", userId)
    .maybeSingle();

  return (data?.role as UserRole | null) ?? null;
}

/**
 * Sets the caller's own role during onboarding. Only ever updates the
 * `role` column — never touches username/email/full_name/avatar_url.
 * Typed to `PublicRole` (excludes ADMIN) so onboarding code can't even
 * construct a call that assigns it, though the real enforcement is
 * server-side: RLS restricts this to the caller's own row (auth.uid() =
 * id), and the profiles.role CHECK constraint rejects anything outside
 * STUDENT/FACULTY/INDUSTRY/INSTITUTION/ADMIN regardless of what's sent.
 * `.select().single()` surfaces a "no rows" error if the profile row
 * doesn't exist, instead of silently succeeding with nothing updated.
 */
export async function updateProfileRole(
  supabase: SupabaseClient,
  userId: string,
  role: PublicRole,
) {
  return supabase.from("profiles").update({ role }).eq("id", userId).select("role").single();
}

/**
 * Creates a new account via Supabase Auth. `full_name` and `username` ride
 * along as auth metadata (`options.data`) — the existing on_auth_user_created
 * trigger (database/migrations/001_profiles.sql) already copies `full_name`
 * into the auto-created profile row. It does NOT copy `username`, so that
 * still needs `syncProfileUsernameFromMetadata` once a session exists (see
 * below) — either immediately, if email confirmation is disabled, or from
 * /auth/callback after the confirmation link is clicked.
 */
export async function signUpWithEmail(
  supabase: SupabaseClient,
  params: {
    email: string;
    password: string;
    fullName: string;
    username: string;
    emailRedirectTo: string;
  },
) {
  return supabase.auth.signUp({
    email: params.email,
    password: params.password,
    options: {
      emailRedirectTo: params.emailRedirectTo,
      data: { full_name: params.fullName, username: params.username },
    },
  });
}

/**
 * Copies `username` from auth metadata into the profile row, but only if
 * the profile doesn't already have one — never overwrites an existing
 * username. Requires an authenticated session (RLS: users can only update
 * their own profile), so this only works once a real session exists.
 * Failures (e.g. the username was claimed by someone else in the
 * meantime) are logged, not thrown — the account itself is still valid
 * either way, and a username can always be set later.
 */
export async function syncProfileUsernameFromMetadata(
  supabase: SupabaseClient,
  userId: string,
  metadata: Record<string, unknown> | null | undefined,
): Promise<void> {
  const username = typeof metadata?.username === "string" ? metadata.username : null;
  if (!username) return;

  const { data: profile } = await supabase
    .from("profiles")
    .select("username")
    .eq("id", userId)
    .maybeSingle();

  if (profile?.username) return;

  const { error } = await supabase.from("profiles").update({ username }).eq("id", userId);
  if (error) {
    console.error("Failed to sync username from signup metadata:", error.message);
  }
}

/**
 * Sends a password-reset link to the given email (Supabase's default
 * email delivery sends a link, not an OTP code — do not assume otherwise).
 * `redirectTo` should point at /auth/callback with a `next=/reset-password`
 * param so the callback route knows to land the user on the reset page
 * once the recovery code is exchanged for a session.
 */
export async function sendPasswordRecoveryEmail(
  supabase: SupabaseClient,
  email: string,
  redirectTo: string,
) {
  return supabase.auth.resetPasswordForEmail(email.trim(), { redirectTo });
}

export async function updatePassword(supabase: SupabaseClient, password: string) {
  return supabase.auth.updateUser({ password });
}

export async function resendSignupVerificationEmail(supabase: SupabaseClient, email: string) {
  return supabase.auth.resend({ type: "signup", email: email.trim() });
}

const FRIENDLY_AUTH_ERRORS: Record<string, string> = {
  "invalid login credentials": "Invalid username or password.",
  "email not confirmed": "Please verify your email address before signing in.",
  "token has expired or is invalid": "Your password reset link is invalid or has expired.",
  "otp expired": "Your password reset link has expired.",
  "invalid otp": "Your password reset link is invalid.",
  "flow state": "Your password reset link is invalid or has expired.",
  "email rate limit exceeded": "Too many attempts. Please wait a moment and try again.",
  over_email_send_rate_limit: "Too many attempts. Please wait a moment and try again.",
  "same password": "New password must be different from your current password.",
  "password should be at least": "Password does not meet the minimum requirements.",
  "user already registered": "That email couldn't be used. Try signing in instead.",
  "already registered": "That email couldn't be used. Try signing in instead.",
  "unable to validate email address": "Please enter a valid email address.",
  "signup_disabled": "New account registration is currently unavailable.",
  "signups not allowed": "New account registration is currently unavailable.",
};

/** Maps a raw Supabase Auth error to a safe, user-facing message. Never echoes the raw error. */
export function getAuthErrorMessage(error: unknown): string {
  const message =
    error && typeof error === "object" && "message" in error
      ? String((error as { message?: unknown }).message ?? "")
      : "";

  const normalized = message.toLowerCase();

  for (const [key, friendly] of Object.entries(FRIENDLY_AUTH_ERRORS)) {
    if (normalized.includes(key)) return friendly;
  }

  if (normalized.includes("fetch") || normalized.includes("network")) {
    return "Network error. Please check your connection and try again.";
  }

  return "Something went wrong. Please try again.";
}
