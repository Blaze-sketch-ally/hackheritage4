import { redirect } from "next/navigation";
import Link from "next/link";
import { BarChart3, Briefcase, Plus, Users, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard, type StatCardProps } from "@/components/dashboard/stat-card";
import { UpcomingEvents } from "@/components/dashboard/upcoming-events";
import { createClient } from "@/lib/supabase/server";
import { fetchProfile } from "@/lib/profile";
import { MOCK_INDUSTRY_EVENTS, type IndustryKpi } from "@/lib/mock/industry-dashboard";
import type { DashboardEvent } from "@/lib/mock/student-dashboard";

const KPI_ICONS: Record<IndustryKpi["id"], LucideIcon> = {
  activePostings: Briefcase,
  totalApplicants: Users,
  shortlisted: Users,
  interviews: BarChart3,
};

const KPI_ACCENTS: Record<IndustryKpi["id"], NonNullable<StatCardProps["accent"]>> = {
  activePostings: "indigo",
  totalApplicants: "blue",
  shortlisted: "emerald",
  interviews: "amber",
};

export default async function IndustryDashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The industry layout already guarantees an authenticated INDUSTRY user
  // reaches this point — this is a defensive fallback, not a second check.
  if (!user) redirect("/login");

  const [
    profile,
    { data: internshipsData },
    { data: jobsData },
    { data: applicationsData },
    { data: interviewsData },
  ] = await Promise.all([
    fetchProfile(supabase, user.id),
    supabase.from("internships").select("id, title, status, created_at").eq("industry_id", user.id),
    supabase.from("jobs").select("id, title, status, created_at").eq("industry_id", user.id),
    supabase
      .from("applications")
      .select("id, status, opportunity_type, internship_id, job_id, created_at")
      .eq("industry_id", user.id),
    supabase.from("interviews").select("id, status, scheduled_at, mode").eq("industry_id", user.id),
  ]);

  const displayName = profile?.full_name || profile?.username || "there";

  const internships = internshipsData ?? [];
  const jobs = jobsData ?? [];
  const applications = applicationsData ?? [];
  const interviews = interviewsData ?? [];

  const publishedInternships = internships.filter((i) => i.status === "PUBLISHED");
  const publishedJobs = jobs.filter((j) => j.status === "PUBLISHED");
  const activePostingsCount = publishedInternships.length + publishedJobs.length;

  const underReviewCount = applications.filter((a) => a.status === "UNDER_REVIEW").length;
  const shortlistedCount = applications.filter((a) => a.status === "SHORTLISTED").length;
  const scheduledInterviews = interviews.filter((i) => i.status === "SCHEDULED");

  const dynamicKpis: IndustryKpi[] = [
    {
      id: "activePostings",
      label: "Active Postings",
      value: String(activePostingsCount),
      helperText: `${publishedInternships.length} internships, ${publishedJobs.length} jobs`,
      trend: activePostingsCount > 0 ? "up" : "neutral",
    },
    {
      id: "totalApplicants",
      label: "Total Applicants",
      value: String(applications.length),
      helperText: applications.length > 0 ? `${underReviewCount} under review` : "No applications yet",
      trend: applications.length > 0 ? "up" : "neutral",
    },
    {
      id: "shortlisted",
      label: "Shortlisted",
      value: String(shortlistedCount),
      helperText: shortlistedCount > 0 ? "Ready for interview" : "Review applicants",
      trend: shortlistedCount > 0 ? "up" : "neutral",
    },
    {
      id: "interviews",
      label: "Interviews",
      value: String(scheduledInterviews.length),
      helperText: scheduledInterviews.length > 0 ? `${scheduledInterviews.length} scheduled` : "No interviews yet",
      trend: scheduledInterviews.length > 0 ? "up" : "neutral",
    },
  ];

  // Combine and sort recent postings
  const recentListings = [
    ...internships.map((item) => ({
      id: item.id,
      title: item.title,
      type: "Internship" as const,
      status: item.status,
      applicants: applications.filter((a) => a.internship_id === item.id).length,
      createdAt: item.created_at,
      href: `/industry/internships/${item.id}`,
    })),
    ...jobs.map((item) => ({
      id: item.id,
      title: item.title,
      type: "Job" as const,
      status: item.status,
      applicants: applications.filter((a) => a.job_id === item.id).length,
      createdAt: item.created_at,
      href: `/industry/jobs/${item.id}`,
    })),
  ]
    .sort((a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime())
    .slice(0, 5);

  const upcomingEvents: DashboardEvent[] =
    scheduledInterviews.length > 0
      ? scheduledInterviews.slice(0, 3).map((iv) => ({
          id: iv.id,
          title: `Candidate Interview (${iv.mode || "Online"})`,
          type: "drive" as const,
          date: new Date(iv.scheduled_at).toLocaleDateString("en-US", {
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit",
          }),
        }))
      : MOCK_INDUSTRY_EVENTS;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Welcome back, {displayName} 👋</h1>
          <p className="text-sm text-muted-foreground">
            Track active postings, review applicants, and coordinate technical interviews.
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="sm" render={<Link href="/industry/jobs/create" />} nativeButton={false}>
            <Plus className="size-3.5 mr-1" /> Post Job
          </Button>
          <Button size="sm" render={<Link href="/industry/internships/create" />} nativeButton={false}>
            <Plus className="size-3.5 mr-1" /> Post Internship
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap items-center justify-between gap-3 rounded-xl border border-border/80 bg-muted/40 px-4 py-3 text-xs text-muted-foreground">
        <div className="flex items-center gap-2">
          <span className="size-2 rounded-full bg-emerald-500 animate-pulse" aria-hidden="true" />
          <span>Talent Pipeline Active: Manage active postings, review verified applicants, and track candidate progress.</span>
        </div>
        <div className="flex items-center gap-3 font-medium text-foreground">
          <Link href="/industry/applicants" className="hover:text-primary transition-colors">
            Applicants →
          </Link>
          <Link href="/industry/internships" className="hover:text-primary transition-colors">
            Internships →
          </Link>
          <Link href="/industry/jobs" className="hover:text-primary transition-colors">
            Jobs →
          </Link>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
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
          <Card>
            <CardHeader>
              <CardTitle>Recent Postings</CardTitle>
              <CardAction>
                <Button variant="ghost" size="sm" render={<Link href="/industry/internships" />} nativeButton={false}>
                  View All
                </Button>
              </CardAction>
            </CardHeader>
            <CardContent className="space-y-2">
              {recentListings.length === 0 ? (
                <div className="flex flex-col items-center justify-center gap-2 rounded-lg border border-dashed py-8 text-center">
                  <p className="text-sm font-medium">No postings yet</p>
                  <p className="text-xs text-muted-foreground">
                    Publish an internship or job opening to start receiving verified student applications.
                  </p>
                  <div className="flex items-center gap-2 mt-2">
                    <Button size="sm" render={<Link href="/industry/internships/create" />} nativeButton={false}>
                      Post an Internship
                    </Button>
                    <Button variant="outline" size="sm" render={<Link href="/industry/jobs/create" />} nativeButton={false}>
                      Post a Job
                    </Button>
                  </div>
                </div>
              ) : (
                recentListings.map((posting) => (
                  <Link
                    key={`${posting.type}-${posting.id}`}
                    href={posting.href}
                    className="flex items-center justify-between gap-3 rounded-lg border border-border/60 px-3 py-2 transition-colors hover:bg-muted/50"
                  >
                    <div className="min-w-0 flex-1">
                      <p className="truncate text-sm font-medium">{posting.title}</p>
                      <p className="text-xs text-muted-foreground">
                        {posting.type} &middot; {posting.applicants} applicant{posting.applicants === 1 ? "" : "s"}
                      </p>
                    </div>
                    <Badge variant={posting.status === "PUBLISHED" ? "secondary" : "outline"}>
                      {posting.status}
                    </Badge>
                  </Link>
                ))
              )}
            </CardContent>
          </Card>
        </div>
        <div className="space-y-6">
          <UpcomingEvents events={upcomingEvents} viewAllHref="/industry/interviews" />
        </div>
      </div>
    </div>
  );
}
