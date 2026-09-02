import { redirect } from "next/navigation";
import { SettingsView } from "@/components/student/settings/settings-view";
import { createClient } from "@/lib/supabase/server";
import { fetchProfile } from "@/lib/profile";
import { fetchStudentProfile } from "@/lib/student/profile";

export default async function StudentSettingsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The student layout already guarantees an authenticated STUDENT reaches
  // this point — this is a defensive fallback, not a second role check.
  if (!user) redirect("/login");

  const [profile, studentProfile] = await Promise.all([
    fetchProfile(supabase, user.id),
    fetchStudentProfile(supabase, user.id),
  ]);

  if (!profile) redirect("/login");

  return (
    <SettingsView
      profile={profile}
      studentProfile={studentProfile}
      email={user.email ?? null}
      emailVerified={Boolean(user.email_confirmed_at)}
    />
  );
}
