import { Handshake } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import type { CompanyInternshipBreakdown } from "@/types/institution-internship";

const DISPLAY_LIMIT = 15;

/** Company participation (Phase 7, Part 12) -- analytics only, not the
 * Industry Partners CRM. */
export function InternshipCompanyBreakdown({ companies }: { companies: CompanyInternshipBreakdown[] }) {
  const rows = companies.slice(0, DISPLAY_LIMIT);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Companies Offering Internships</CardTitle>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <EmptyState icon={Handshake} title="No company activity yet" />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead className="text-right">Opportunities</TableHead>
                <TableHead className="text-right">Applicants</TableHead>
                <TableHead className="text-right">Selected</TableHead>
                <TableHead className="text-right">Completed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.company_name}>
                  <TableCell className="font-medium">{c.company_name}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.opportunities}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.applicants}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.selected}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.completed}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
