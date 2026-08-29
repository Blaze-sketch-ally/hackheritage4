import { redirect } from "next/navigation";
import { ProfileHeader } from "@/components/student/profile/profile-header";
import { StudentProfileForm } from "@/components/student/profile/student-profile-form";
import { createClient } from "@/lib/supabase/server";
import { fetchProfile } from "@/lib/profile";
import { fetchStudentProfile, getProfileCompletion } from "@/lib/student/profile";

export default async function StudentProfilePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  const profile = await fetchProfile(supabase, user.id);
  if (!profile) redirect("/login");

  const studentProfile = await fetchStudentProfile(supabase, user.id);
  const completion = getProfileCompletion(profile, studentProfile);

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <ProfileHeader profile={profile} completion={completion} />
      <StudentProfileForm profile={profile} studentProfile={studentProfile} />
    </div>
  );
}
