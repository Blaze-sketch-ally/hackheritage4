import Link from "next/link";
import { Building2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import type { DepartmentInternshipBreakdown } from "@/types/institution-internship";

/**
 * Department participation (Phase 7, Part 11). `student_count` and
 * `selected_count` come straight from institution_department_service.
 * list_departments -- the same rows /institution/departments renders --
 * `participants` / `completed_count` are the only internship-specific
 * additions. Uses the real `departments` entity, never free text.
 */
export function InternshipDepartmentBreakdown({
  departments,
}: {
  departments: DepartmentInternshipBreakdown[];
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Internship Participation by Department</CardTitle>
      </CardHeader>
      <CardContent>
        {departments.length === 0 ? (
          <EmptyState icon={Building2} title="No department data yet" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Department</TableHead>
                <TableHead className="text-right">Students</TableHead>
                <TableHead className="text-right">Participants</TableHead>
                <TableHead className="text-right">Participation Rate</TableHead>
                <TableHead className="text-right">Selected</TableHead>
                <TableHead className="text-right">Completed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {departments.map((d) => (
                <TableRow key={d.id}>
                  <TableCell className="font-medium">
                    <Link href={`/institution/departments/${d.id}`} className="hover:underline">
                      {d.name}
                    </Link>
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{d.student_count}</TableCell>
                  <TableCell className="text-right tabular-nums">{d.participants}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {d.student_count === 0 ? "N/A" : d.participation_rate != null ? `${d.participation_rate}%` : "—"}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{d.selected_count}</TableCell>
                  <TableCell className="text-right tabular-nums">{d.completed_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
