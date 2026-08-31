import { redirect } from "next/navigation";
import Link from "next/link";
import { BarChart3, Briefcase, Users, type LucideIcon } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { RecruitmentFunnel } from "@/components/industry/recruitment-funnel";
import { StatCard, type StatCardProps } from "@/components/dashboard/stat-card";
import { UpcomingEvents } from "@/components/dashboard/upcoming-events";
import { createClient } from "@/lib/supabase/server";
import { fetchProfile } from "@/lib/profile";
import {
  MOCK_HIRING_PIPELINE,
  MOCK_INDUSTRY_EVENTS,
  MOCK_INDUSTRY_KPIS,
  MOCK_RECENT_POSTINGS,
  type IndustryKpi,
} from "@/lib/mock/industry-dashboard";

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

const STATUS_VARIANT: Record<(typeof MOCK_RECENT_POSTINGS)[number]["status"], "secondary" | "outline"> = {
  Open: "secondary",
  "Closing Soon": "outline",
  Closed: "outline",
};

export default async function IndustryDashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The industry layout already guarantees an authenticated INDUSTRY user
  // reaches this point — this is a defensive fallback, not a second check.
  if (!user) redirect("/login");

  const profile = await fetchProfile(supabase, user.id);
  const displayName = profile?.full_name || profile?.username || "there";

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Welcome back, {displayName} 👋</h1>
          <p className="text-sm text-muted-foreground">
            Track postings, applicants, and your hiring pipeline.
          </p>
        </div>
        <Button render={<Link href="/industry/internships/create" />} nativeButton={false}>
          Post an Opportunity
        </Button>
      </div>

      <div className="rounded-lg border border-dashed border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-muted-foreground">
        The numbers below are demo data — real postings, applications, and matching land in a later
        phase. The navigation and layout are fully real.
      </div>

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {MOCK_INDUSTRY_KPIS.map((kpi) => (
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
          <RecruitmentFunnel stages={MOCK_HIRING_PIPELINE} />

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
              {MOCK_RECENT_POSTINGS.map((posting) => (
                <div
                  key={posting.id}
                  className="flex items-center justify-between gap-3 rounded-lg border border-border/60 px-3 py-2"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm font-medium">{posting.title}</p>
                    <p className="text-xs text-muted-foreground">
                      {posting.type} &middot; {posting.applicants} applicants
                    </p>
                  </div>
                  <Badge variant={STATUS_VARIANT[posting.status]}>{posting.status}</Badge>
                </div>
              ))}
            </CardContent>
          </Card>
        </div>
        <div className="space-y-6">
          <UpcomingEvents events={MOCK_INDUSTRY_EVENTS} viewAllHref="/industry/interviews" />
        </div>
      </div>
    </div>
  );
}
