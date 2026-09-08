import { Briefcase } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/common/empty-state";
import { Badge } from "@/components/ui/badge";
import type { OpportunitiesOverview as OpportunitiesOverviewData } from "@/types/institution-analytics";

/** Jobs/internships are platform-wide postings (no institution-ownership
 * relationship exists in the schema) — labeled honestly as such, never
 * "your institution's jobs". `applicants_from_your_institution` IS real
 * institution-specific data: how many of YOUR linked students applied. */
export function OpportunitiesOverview({ opportunities }: { opportunities: OpportunitiesOverviewData }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Opportunities</CardTitle>
        <p className="text-xs text-muted-foreground">
          Published across the platform — {opportunities.active_jobs} active job
          {opportunities.active_jobs === 1 ? "" : "s"}, {opportunities.active_internships} active
          internship{opportunities.active_internships === 1 ? "" : "s"}.
        </p>
      </CardHeader>
      <CardContent>
        {opportunities.recent.length === 0 ? (
          <EmptyState icon={Briefcase} title="No recent opportunities" />
        ) : (
          <ul className="divide-y">
            {opportunities.recent.map((opp) => (
              <li key={opp.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{opp.title}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {opp.company_name ?? "Unknown company"} ·{" "}
                    <Badge variant="outline" className="align-middle">
                      {opp.opportunity_type === "JOB" ? "Job" : "Internship"}
                    </Badge>
                  </p>
                </div>
                <span className="shrink-0 text-right text-xs text-muted-foreground">
                  <span className="font-semibold text-foreground tabular-nums">
                    {opp.applicants_from_your_institution}
                  </span>{" "}
                  from your students
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
