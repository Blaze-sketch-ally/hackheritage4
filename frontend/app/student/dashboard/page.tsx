import Link from "next/link";
import { Button } from "@/components/ui/button";
import { DashboardAiSuggestions } from "@/components/student/dashboard/dashboard-ai-suggestions";
import { DashboardAnnouncements } from "@/components/student/dashboard/dashboard-announcements";
import { DashboardApplications } from "@/components/student/dashboard/dashboard-applications";
import { DashboardKpis } from "@/components/student/dashboard/dashboard-kpis";
import { DashboardLearning } from "@/components/student/dashboard/dashboard-learning";
import { DashboardRecommendations } from "@/components/student/dashboard/dashboard-recommendations";
import { ProfileCompletion } from "@/components/student/profile-completion";
import { SkillOverview } from "@/components/student/skill-overview";
import { createClient } from "@/lib/supabase/server";
import { fetchProfile } from "@/lib/profile";
import { fetchStudentProfile, getProfileCompletion } from "@/lib/student/profile";
import { fetchStudentSkills } from "@/lib/student/skills";
import { summarizeSkills } from "@/lib/student/dashboard";

export default async function StudentDashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The layout already guarantees an authenticated STUDENT reaches this
  // point — this is just TypeScript narrowing, not a second auth check.
  if (!user) return null;

  // Identity + skills come straight from Supabase (RLS-scoped) in this
  // server component. The API-backed sections (skill gap, applications,
  // learning, assessments) load client-side through the FastAPI bridge,
  // each in its own component so one failing section never blanks the page.
  const [profile, studentProfile, studentSkills] = await Promise.all([
    fetchProfile(supabase, user.id),
    fetchStudentProfile(supabase, user.id),
    fetchStudentSkills(supabase, user.id),
  ]);

  const completion = getProfileCompletion(profile, studentProfile);
  const displayName = profile?.full_name || profile?.username || "Student";
  const skillsSummary = summarizeSkills(studentSkills);

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Welcome back, {displayName}! 👋</h1>
          <p className="text-sm text-muted-foreground">
            Track your progress, build your skills and discover opportunities.
          </p>
        </div>
        <Button render={<Link href="/student/profile" />} nativeButton={false}>
          Update Profile
        </Button>
      </div>

      <DashboardKpis skills={skillsSummary} />

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <SkillOverview studentSkills={studentSkills} />
          <DashboardApplications />
          <DashboardLearning />
        </div>
        <div className="space-y-6">
          <ProfileCompletion percent={completion} />
          <DashboardRecommendations />
          <DashboardAnnouncements />
          <DashboardAiSuggestions />
        </div>
      </div>
    </div>
  );
}
