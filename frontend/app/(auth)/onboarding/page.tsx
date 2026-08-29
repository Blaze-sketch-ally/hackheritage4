import { redirect } from "next/navigation";
import { AuthShell } from "@/components/auth/auth-shell";
import { RoleSelection } from "@/components/onboarding/role-selection";
import { createClient } from "@/lib/supabase/server";
import { fetchProfileRole, getPostLoginRedirectPath } from "@/lib/auth";

export default async function OnboardingPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) {
    redirect("/login");
  }

  // Already has a role (e.g. revisited /onboarding directly) — this page
  // is only for the one-time role selection, not for changing it later.
  const role = await fetchProfileRole(supabase, user.id);
  if (role) {
    redirect(getPostLoginRedirectPath(role));
  }

  return (
    <AuthShell
      title="Welcome to AIC Portal"
      description="Let's personalize your experience — what best describes you?"
      contentClassName="max-w-2xl"
    >
      <RoleSelection userId={user.id} />
    </AuthShell>
  );
}
