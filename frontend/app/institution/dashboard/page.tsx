import { redirect } from "next/navigation";
import Link from "next/link";
import { Card, CardAction, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { DepartmentTable } from "@/components/institution/department-table";
import { InstitutionKpis } from "@/components/institution/institution-kpis";
import { PlacementChart } from "@/components/institution/placement-chart";
import { SkillGapChart } from "@/components/institution/skill-gap-chart";
import { UpcomingEvents } from "@/components/dashboard/upcoming-events";
import { createClient } from "@/lib/supabase/server";
import { fetchProfile } from "@/lib/profile";
import {
  MOCK_DEPARTMENTS,
  MOCK_INSTITUTION_EVENTS,
  MOCK_INSTITUTION_KPIS,
  MOCK_PLACEMENT_TREND,
  MOCK_TOP_SKILL_GAPS,
} from "@/lib/mock/institution-dashboard";

export default async function InstitutionDashboardPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The institution layout already guarantees an authenticated
  // INSTITUTION user reaches this point — a defensive fallback only.
  if (!user) redirect("/login");

  const profile = await fetchProfile(supabase, user.id);
  const displayName = profile?.full_name || profile?.username || "there";

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Welcome back, {displayName} 👋</h1>
        <p className="text-sm text-muted-foreground">
          Track student skill trends, placements, and industry partnerships.
        </p>
      </div>

      <div className="rounded-lg border border-dashed border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-muted-foreground">
        The numbers and charts below are demo data — real cross-student analytics land in a later
        phase. The navigation and layout are fully real.
      </div>

      <InstitutionKpis kpis={MOCK_INSTITUTION_KPIS} />

      <div className="grid gap-6 xl:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle>Placement Trend</CardTitle>
            <CardDescription>Students placed per month — demo data.</CardDescription>
          </CardHeader>
          <CardContent>
            <PlacementChart data={MOCK_PLACEMENT_TREND} />
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Top Skill Gaps</CardTitle>
            <CardDescription>Lowest average scores across your students — demo data.</CardDescription>
            <CardAction>
              <Button variant="ghost" size="sm" render={<Link href="/institution/skill-gaps" />} nativeButton={false}>
                View All
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            <SkillGapChart data={MOCK_TOP_SKILL_GAPS} />
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 xl:grid-cols-3">
        <Card className="xl:col-span-2">
          <CardHeader>
            <CardTitle>Departments</CardTitle>
            <CardAction>
              <Button variant="ghost" size="sm" render={<Link href="/institution/departments" />} nativeButton={false}>
                View All
              </Button>
            </CardAction>
          </CardHeader>
          <CardContent>
            <DepartmentTable departments={MOCK_DEPARTMENTS} />
          </CardContent>
        </Card>
        <div>
          <UpcomingEvents events={MOCK_INSTITUTION_EVENTS} viewAllHref="/institution/events" />
        </div>
      </div>
    </div>
  );
}
