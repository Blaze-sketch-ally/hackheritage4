"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, ChevronRight } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { getPlacementOverview } from "@/lib/institution/placements";
import type { PlacementOverviewResponse } from "@/types/institution-placement";

/**
 * Minimal, additive-only dashboard entry point into Placement Drive
 * Management (Part 22) -- a separate fetch from the dashboard's own
 * GET /api/v1/institution/overview aggregation, so it never changes that
 * response shape or its existing student/department analytics
 * definitions. Renders nothing while loading or on error, and nothing at
 * all once loaded if there are zero drives -- never a fabricated "0
 * drives" card competing for attention on an otherwise-real dashboard.
 */
export function PlacementDrivesLink() {
  const [overview, setOverview] = useState<PlacementOverviewResponse | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPlacementOverview()
      .then((data) => {
        if (!cancelled) setOverview(data);
      })
      .catch(() => {
        // Silent -- this is a supplementary link, not a page-critical
        // metric; the dashboard's own overview already reports real errors.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (overview === null || overview.active_drives + overview.completed_drives === 0) return null;

  return (
    <Link href="/institution/placements">
      <Card className="transition-colors hover:bg-muted/40">
        <CardContent className="flex items-center justify-between gap-3">
          <div className="flex items-center gap-3">
            <span className="flex size-9 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
              <Briefcase className="size-4.5" aria-hidden="true" />
            </span>
            <div>
              <p className="text-sm font-medium">Placement Drives</p>
              <p className="text-xs text-muted-foreground">
                {overview.active_drives} active · {overview.placed_students} students placed
              </p>
            </div>
          </div>
          <ChevronRight className="size-4 text-muted-foreground" aria-hidden="true" />
        </CardContent>
      </Card>
    </Link>
  );
}
