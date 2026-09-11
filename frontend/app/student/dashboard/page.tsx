import Link from "next/link";
import { Award, Briefcase, GraduationCap, Target, TrendingUp, type LucideIcon } from "lucide-react";
import { ApplicationTracker } from "@/components/dashboard/application-tracker";
import { Button } from "@/components/ui/button";
import { DashboardLearning } from "@/components/student/dashboard/dashboard-learning";
import { DashboardRecommendations } from "@/components/student/dashboard/dashboard-recommendations";
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
  MOCK_EVENTS,
  type DashboardKpi,
  type SkillRadarPoint,
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

  const [
    profile,
    studentProfile,
    studentSkills,
    { data: applicationsData },
    { data: attemptsData },
    { count: projectCount },
    { count: certCount },
  ] = await Promise.all([
    fetchProfile(supabase, user.id),
    fetchStudentProfile(supabase, user.id),
    fetchStudentSkills(supabase, user.id),
    supabase
      .from("applications")
      .select("id, status, match_score, created_at")
      .eq("student_id", user.id),
    supabase
      .from("assessment_attempts")
      .select("id, status, percentage")
      .eq("student_id", user.id)
      .eq("status", "COMPLETED"),
    supabase
      .from("portfolio_projects")
      .select("id", { count: "exact", head: true })
      .eq("student_id", user.id),
    supabase
      .from("portfolio_certifications")
      .select("id", { count: "exact", head: true })
      .eq("student_id", user.id),
  ]);

  const displayName = profile?.full_name || profile?.username || "Student";
  const applications = applicationsData ?? [];
  const completedAttempts = attemptsData ?? [];
  const totalProjects = projectCount ?? 0;
  const totalCerts = certCount ?? 0;
  const completion = getProfileCompletion(profile, studentProfile);
  const verifiedSkillsCount = studentSkills.filter((s) => s.is_verified).length;

  // 1. Skill Score
  let skillScoreVal = "0%";
  let skillScoreHelper = "No assessments taken yet";
  let skillScoreTrend: "up" | "neutral" | "down" = "neutral";
  if (completedAttempts.length > 0) {
    const avgScore = Math.round(
      completedAttempts.reduce((sum, a) => sum + (Number(a.percentage) || 0), 0) /
        completedAttempts.length
    );
    skillScoreVal = `${avgScore}%`;
    skillScoreHelper = `${completedAttempts.length} assessment${
      completedAttempts.length === 1 ? "" : "s"
    } completed`;
    skillScoreTrend = avgScore >= 70 ? "up" : "neutral";
  } else if (studentSkills.length > 0) {
    skillScoreVal = `${studentSkills.length} Skills`;
    skillScoreHelper = "Self-reported, unverified";
  }

  // 2. Career Readiness
  const readinessPercentage = Math.min(
    100,
    Math.round(completion * 0.7 + Math.min(verifiedSkillsCount, 5) * 6)
  );
  const readinessHelper =
    readinessPercentage >= 75
      ? "Job-ready profile"
      : completion < 50
      ? `${completion}% profile complete`
      : "Verify skills with tests";

  // 3. Profile & Skills
  const skillsVal = String(studentSkills.length);
  const skillsHelper =
    verifiedSkillsCount > 0
      ? `${verifiedSkillsCount} verified by assessment`
      : studentSkills.length > 0
      ? "Take tests to verify"
      : "Add skills to unlock matching";

  // 4. Applications
  const activeApps = applications.filter(
    (a) => a.status !== "WITHDRAWN" && a.status !== "REJECTED"
  );
  const shortlistedCount = applications.filter(
    (a) => a.status === "SHORTLISTED" || a.status === "INTERVIEW_SCHEDULED"
  ).length;
  const appsVal = String(activeApps.length);
  const appsHelper =
    shortlistedCount > 0
      ? `${shortlistedCount} shortlisted`
      : applications.length > 0
      ? `${applications.length} total submitted`
      : "Explore internships & jobs";

  // 5. Portfolio & Credentials
  const totalPortfolioItems = totalProjects + totalCerts;
  const portfolioVal = String(totalPortfolioItems);
  const portfolioHelper = `${totalProjects} projects, ${totalCerts} certs`;

  const dynamicKpis: DashboardKpi[] = [
    {
      id: "skillScore",
      label: "Overall Skill Score",
      value: skillScoreVal,
      helperText: skillScoreHelper,
      trend: skillScoreTrend,
    },
    {
      id: "careerReadiness",
      label: "Career Readiness",
      value: `${readinessPercentage}%`,
      helperText: readinessHelper,
      trend: readinessPercentage >= 70 ? "up" : "neutral",
    },
    {
      id: "learningProgress",
      label: "Profile & Skills",
      value: skillsVal,
      helperText: skillsHelper,
      trend: studentSkills.length > 0 ? "up" : "neutral",
    },
    {
      id: "applications",
      label: "Active Applications",
      value: appsVal,
      helperText: appsHelper,
      trend: activeApps.length > 0 ? "up" : "neutral",
    },
    {
      id: "achievements",
      label: "Portfolio Items",
      value: portfolioVal,
      helperText: portfolioHelper,
      trend: totalPortfolioItems > 0 ? "up" : "neutral",
    },
  ];

  // Real Application Stages
  const applicationStages = [
    { label: "Applied", count: applications.filter((a) => a.status === "APPLIED").length },
    { label: "Under Review", count: applications.filter((a) => a.status === "UNDER_REVIEW").length },
    { label: "Shortlisted", count: applications.filter((a) => a.status === "SHORTLISTED").length },
    { label: "Interview", count: applications.filter((a) => a.status === "INTERVIEW_SCHEDULED").length },
    { label: "Selected / Offer", count: applications.filter((a) => a.status === "SELECTED").length },
  ];

  // Dynamic Skill Radar from studentSkills
  const categoriesMap = new Map<string, number[]>();
  for (const s of studentSkills) {
    const cat = s.skill.category?.name || "General";
    const score =
      s.proficiency_score != null
        ? s.proficiency_score
        : s.proficiency_level === "Expert"
        ? 95
        : s.proficiency_level === "Advanced"
        ? 80
        : s.proficiency_level === "Intermediate"
        ? 60
        : 40;
    const existing = categoriesMap.get(cat) || [];
    existing.push(score);
    categoriesMap.set(cat, existing);
  }

  let skillRadar: SkillRadarPoint[] = [];
  if (categoriesMap.size >= 3) {
    skillRadar = Array.from(categoriesMap.entries()).map(([category, scores]) => ({
      category,
      score: Math.round(scores.reduce((a, b) => a + b, 0) / scores.length),
    }));
  } else {
    // Standard baseline radar axes with real scores mapped where available
    const baseAxes = ["Programming", "Problem Solving", "Database", "System", "Web"];
    skillRadar = baseAxes.map((axis) => {
      const scores = categoriesMap.get(axis);
      if (scores && scores.length > 0) {
        return { category: axis, score: Math.round(scores.reduce((a, b) => a + b, 0) / scores.length) };
      }
      return { category: axis, score: studentSkills.length > 0 ? 35 : 15 };
    });
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Welcome back, {displayName}! 👋</h1>
          <p className="text-sm text-muted-foreground">
            Track your progress, build verified skills, and discover opportunities.
          </p>
        </div>
        <Button render={<Link href="/student/profile" />} nativeButton={false}>
          Update Profile
        </Button>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-5">
        {dynamicKpis.map((kpi) => (
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
          <SkillOverview radar={skillRadar} studentSkills={studentSkills} />
          <RecommendationTabs />
          <ApplicationTracker stages={applicationStages} />
          <DashboardLearning />
        </div>
        <div className="space-y-6">
          <ProfileCompletion percent={completion} />
          <UpcomingEvents events={MOCK_EVENTS} viewAllHref="/student/events" />
          <DashboardRecommendations />
        </div>
      </div>
    </div>
  );
}
