import { NextResponse } from "next/server";
import { createClient } from "@/lib/supabase/server";
import {
  fetchProfileRole,
  getPostLoginRedirectPath,
  getSafeRedirectPath,
  syncProfileUsernameFromMetadata,
} from "@/lib/auth";

// Handles three distinct flows that all land here with a `?code=` to
// exchange for a session:
//   - Google OAuth (no `next` param): role-based dashboard/onboarding redirect.
//   - Email/password registration confirmation (no `next` param either —
//     same redirect as OAuth is exactly right: role is still null, so it
//     lands on /onboarding). The username chosen at signup lives in auth
//     metadata (the trigger only copies full_name), so it's synced into
//     the profile here, now that a real session exists to satisfy RLS.
//   - Password recovery (`next=/reset-password`, set by the forgot-password
//     form's redirectTo): land on the reset page instead — a recovery
//     session isn't a normal sign-in, so it must NOT get the role redirect.
export async function GET(request: Request) {
  const { searchParams, origin } = new URL(request.url);
  const code = searchParams.get("code");
  const next = getSafeRedirectPath(searchParams.get("next"));

  if (code) {
    const supabase = await createClient();
    const { data, error } = await supabase.auth.exchangeCodeForSession(code);

    if (!error && data.user) {
      if (next) {
        return NextResponse.redirect(`${origin}${next}`);
      }

      await syncProfileUsernameFromMetadata(supabase, data.user.id, data.user.user_metadata);

      // A brand-new Google/registered user has a profile row (auto-created
      // by the on_auth_user_created trigger) but no role yet — send them
      // to onboarding instead of assuming a role.
      const role = await fetchProfileRole(supabase, data.user.id);
      return NextResponse.redirect(`${origin}${getPostLoginRedirectPath(role)}`);
    }
  }

  // Exchange failed (expired/already-used code) or no code at all. A failed
  // recovery attempt should land back on /reset-password, which shows its
  // own "invalid or expired" state rather than a misleading OAuth error.
  if (next === "/reset-password") {
    return NextResponse.redirect(`${origin}/reset-password`);
  }

  return NextResponse.redirect(`${origin}/login?error=oauth_failed`);
}
