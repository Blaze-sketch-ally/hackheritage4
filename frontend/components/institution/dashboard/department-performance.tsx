import Link from "next/link";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { EmptyState } from "@/components/common/empty-state";
import { Building2 } from "lucide-react";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { DepartmentMetric } from "@/types/institution-analytics";

export function DepartmentPerformance({ departments }: { departments: DepartmentMetric[] }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Department Performance</CardTitle>
        <p className="text-xs text-muted-foreground">
          Grouped by each linked student&apos;s assigned department. Students not yet assigned to a
          department appear under &quot;Unassigned&quot; —{" "}
          <Link href="/institution/departments" className="text-indigo-600 hover:underline dark:text-indigo-400">
            manage departments
          </Link>
          .
        </p>
      </CardHeader>
      <CardContent>
        {departments.length === 0 ? (
          <EmptyState
            icon={Building2}
            title="No department data yet"
            description="This appears once students are linked to your institution."
          />
        ) : (
          <div className="overflow-x-auto">
            <Table className="min-w-[500px]">
              <TableHeader>
                <TableRow>
                  <TableHead>Department</TableHead>
                  <TableHead className="text-right">Students</TableHead>
                  <TableHead className="text-right">Placed</TableHead>
                  <TableHead className="text-right">Placement %</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {departments.map((d) => (
                  <TableRow key={d.department}>
                    <TableCell className="font-medium">
                      {d.department_id ? (
                        <Link
                          href={`/institution/departments/${d.department_id}`}
                          className="hover:underline"
                        >
                          {d.department}
                        </Link>
                      ) : (
                        d.department
                      )}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{d.total_students}</TableCell>
                    <TableCell className="text-right tabular-nums">{d.placed_students}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {d.placement_percentage != null ? `${d.placement_percentage}%` : "—"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
