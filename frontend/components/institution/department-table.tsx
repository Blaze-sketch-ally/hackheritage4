import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { DepartmentRow } from "@/lib/mock/institution-dashboard";

export function DepartmentTable({ departments }: { departments: DepartmentRow[] }) {
  return (
    <Table>
      <TableHeader>
        <TableRow>
          <TableHead>Department</TableHead>
          <TableHead className="text-right">Students</TableHead>
          <TableHead className="text-right">Avg. Skill Score</TableHead>
          <TableHead className="text-right">Placement Rate</TableHead>
        </TableRow>
      </TableHeader>
      <TableBody>
        {departments.map((dept) => (
          <TableRow key={dept.id}>
            <TableCell className="font-medium">{dept.name}</TableCell>
            <TableCell className="text-right tabular-nums">{dept.students}</TableCell>
            <TableCell className="text-right tabular-nums">{dept.avgSkillScore}%</TableCell>
            <TableCell className="text-right tabular-nums">{dept.placementRate}%</TableCell>
          </TableRow>
        ))}
      </TableBody>
    </Table>
  );
}
