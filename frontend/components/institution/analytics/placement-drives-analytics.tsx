"use client";

import Link from "next/link";
import { Briefcase } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import type { PlacementAnalytics } from "@/types/institution-analytics-report";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  OPEN: "default",
  IN_PROGRESS: "default",
  COMPLETED: "secondary",
  CANCELLED: "destructive",
  DRAFT: "outline",
};

/**
 * Placement Drive Analytics (Phase 6, Part 9). `placements.drives` is the
 * exact same per-drive rows /institution/placements renders
 * (institution_placement_service.list_drives, reused verbatim) --
 * selection_rate is computed here as selected/applied and shown as N/A
 * when applied_count is 0, never a fabricated 0%. Always
 * institution-wide, unaffected by this page's own department/batch
 * filters (a drive has its own eligibility criteria, independent of
 * either).
 */
export function PlacementDrivesAnalytics({ placements }: { placements: PlacementAnalytics }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Placement Drives</CardTitle>
        <p className="text-xs text-muted-foreground">
          Institution-wide. {placements.total_drives} total ({placements.active_drives} active,{" "}
          {placements.completed_drives} completed, {placements.cancelled_drives} cancelled,{" "}
          {placements.draft_drives} draft)
          {placements.average_applicants_per_drive != null
            ? ` · ${placements.average_applicants_per_drive} applicants/drive on average`
            : ""}
          .
        </p>
      </CardHeader>
      <CardContent>
        {placements.drives.length === 0 ? (
          <EmptyState
            icon={Briefcase}
            title="No placement drives yet"
            description="Coordinate your first drive from a published job to see drive-level analytics here."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Drive</TableHead>
                <TableHead>Company</TableHead>
                <TableHead>Status</TableHead>
                <TableHead className="text-right">Eligible</TableHead>
                <TableHead className="text-right">Applicants</TableHead>
                <TableHead className="text-right">Selected</TableHead>
                <TableHead className="text-right">Selection Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {placements.drives.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="font-medium">
                    <Link href={`/institution/placements/${d.id}`} className="hover:underline">
                      {d.title}
                    </Link>
                  </TableCell>
                  <TableCell className="text-muted-foreground">{d.company_name ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant={STATUS_VARIANT[d.status] ?? "outline"}>{d.status}</Badge>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{d.eligible_count}</TableCell>
                  <TableCell className="text-right tabular-nums">{d.applied_count}</TableCell>
                  <TableCell className="text-right tabular-nums">{d.selected_count}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {d.selection_rate != null ? `${d.selection_rate}%` : "N/A"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
