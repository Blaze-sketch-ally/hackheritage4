import Link from "next/link";
import { Award, Briefcase, GraduationCap, Target, TrendingUp, type LucideIcon } from "lucide-react";
import { AiRecommendations } from "@/components/student/ai-recommendations";
import { ApplicationTracker } from "@/components/dashboard/application-tracker";
import { Button } from "@/components/ui/button";
import { ProfileCompletion } from "@/components/student/profile-completion";
import { RecommendationTabs } from "@/components/student/recommendation-tabs";
import { SkillOverview } from "@/components/student/skill-overview";
import { StatCard, type StatCardProps } from "@/components/dashboard/stat-card";
import { UpcomingEvents } from "@/components/dashboard/upcoming-events";
import { createClient } from "@/lib/supabase/server";
import { fetchProfile } from "@/lib/profile";
import { fetchStudentProfile, getProfileCompletion } from "@/lib/student/profile";
import { fetchStudentSkills } from "@/lib/student/skills";
import {
  MOCK_APPLICATION_STAGES,
  MOCK_EVENTS,
  MOCK_KPIS,
  MOCK_SKILL_RADAR,
  type DashboardKpi,
} from "@/lib/mock/student-dashboard";

const KPI_ICONS: Record<DashboardKpi["id"], LucideIcon> = {
  skillScore: Target,
  careerReadiness: TrendingUp,
  learningProgress: GraduationCap,
  applications: Briefcase,
  achievements: Award,
};

const KPI_ACCENTS: Record<DashboardKpi["id"], NonNullable<StatCardProps["accent"]>> = {
  skillScore: "indigo",
  careerReadiness: "violet",
  learningProgress: "blue",
  applications: "amber",
  achievements: "emerald",
};

export default async function StudentDashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The layout already guarantees an authenticated STUDENT reaches this
  // point — this is just TypeScript narrowing, not a second auth check.
  if (!user) return null;

  const profile = await fetchProfile(supabase, user.id);
  const studentProfile = await fetchStudentProfile(supabase, user.id);
  const studentSkills = await fetchStudentSkills(supabase, user.id);
  const completion = getProfileCompletion(profile, studentProfile);
  const displayName = profile?.full_name || profile?.username || "Student";

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

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {MOCK_KPIS.map((kpi) => (
          <StatCard
            key={kpi.id}
            label={kpi.label}
            value={kpi.value}
            helperText={kpi.helperText}
            trend={kpi.trend}
            icon={KPI_ICONS[kpi.id]}
            accent={KPI_ACCENTS[kpi.id]}
          />
        ))}
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <div className="space-y-6 xl:col-span-2">
          <SkillOverview radar={MOCK_SKILL_RADAR} studentSkills={studentSkills} />
          <RecommendationTabs />
          <ApplicationTracker stages={MOCK_APPLICATION_STAGES} />
        </div>
        <div className="space-y-6">
          <ProfileCompletion percent={completion} />
          <UpcomingEvents events={MOCK_EVENTS} viewAllHref="/student/events" />
          <AiRecommendations />
        </div>
      </div>
    </div>
  );
}
