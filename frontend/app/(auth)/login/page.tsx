import { Suspense } from "react";
import { redirect } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { LoginForm } from "@/components/auth/login-form";
import { createClient } from "@/lib/supabase/server";
import { getPostLoginRedirectPath } from "@/lib/auth";
import { fetchProfile } from "@/lib/profile";

// QA finding F1-3: an already-authenticated user landing on /login was shown
// the sign-in form instead of being sent to their own area. Mirror the
// server-side redirect the role layouts (app/industry/layout.tsx etc.)
// already use: resolve the role and bounce to its destination
// (getPostLoginRedirectPath falls back to /onboarding when the role is
// unset). Unauthenticated visitors still get the form.
export default async function LoginPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (user) {
    const profile = await fetchProfile(supabase, user.id);
    redirect(getPostLoginRedirectPath(profile?.role));
  }

  return (
    <AuthShell title="Welcome back 👋" description="Sign in to continue to your account">
      <Suspense fallback={null}>
        <LoginForm />
      </Suspense>
    </AuthShell>
  );
}
