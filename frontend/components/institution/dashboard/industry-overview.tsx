import Link from "next/link";
import { Handshake } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import type {
  CollaborationsOverview,
  IndustryOverview as IndustryOverviewData,
} from "@/types/institution-analytics";

export function IndustryOverview({
  industry,
  collaborations,
}: {
  industry: IndustryOverviewData;
  collaborations: CollaborationsOverview;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Industry &amp; Collaborations</CardTitle>
        <p className="text-xs text-muted-foreground">
          Company directory is platform-wide; collaborations below are proposals addressed to your
          institution specifically.
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            ["Industry partners", industry.total_industry_partners],
            ["Recent postings (30d)", industry.recent_postings_count],
            ["Pending requests", collaborations.pending],
            ["Active collaborations", collaborations.active],
          ].map(([label, value]) => (
            <div key={label as string} className="rounded-lg bg-muted/50 px-3 py-2">
              <p className="text-xl font-semibold tabular-nums">{value as number}</p>
              <p className="text-[11px] text-muted-foreground">{label}</p>
            </div>
          ))}
        </div>

        {collaborations.pending > 0 ? (
          <div className="flex items-center justify-between gap-3 rounded-lg border border-dashed px-3 py-2">
            <p className="flex items-center gap-1.5 text-sm">
              <Handshake className="size-4 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
              {collaborations.pending} collaboration request{collaborations.pending === 1 ? "" : "s"}{" "}
              waiting on your response
            </p>
            <Button size="sm" variant="outline" render={<Link href="/institution/collaborations" />}>
              Review
            </Button>
          </div>
        ) : (
          <Button size="sm" variant="outline" render={<Link href="/institution/collaborations" />}>
            View all collaborations
          </Button>
        )}
      </CardContent>
    </Card>
  );
}
