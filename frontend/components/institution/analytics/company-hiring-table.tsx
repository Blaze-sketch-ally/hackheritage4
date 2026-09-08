import { Handshake } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import type { CompanyHiring } from "@/types/institution-analytics-report";

const DISPLAY_LIMIT = 15;

/**
 * Company / Hiring Analytics (Phase 6, Part 10) -- analytics only, not
 * the Industry Partners CRM. Covers EVERY application your institution's
 * students have submitted (direct or drive-coordinated), always
 * institution-wide. `selected_offers` (application count) is kept
 * distinct from `unique_students_placed` -- a student can hold multiple
 * selected offers from the same company only if they applied to more
 * than one posting there.
 */
export function CompanyHiringTable({ companies }: { companies: CompanyHiring[] }) {
  const rows = companies.slice(0, DISPLAY_LIMIT);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Companies Hiring Your Students</CardTitle>
        <p className="text-xs text-muted-foreground">
          Institution-wide, sorted by selected offers. Every application your students have submitted, not limited
          to institution-coordinated drives.
        </p>
      </CardHeader>
      <CardContent>
        {rows.length === 0 ? (
          <EmptyState
            icon={Handshake}
            title="No company activity yet"
            description="This appears once your students start applying to jobs or internships."
          />
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead className="text-right">Postings</TableHead>
                <TableHead className="text-right">Applicants</TableHead>
                <TableHead className="text-right">Selected Offers</TableHead>
                <TableHead className="text-right">Unique Students Placed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {rows.map((c) => (
                <TableRow key={c.company_name}>
                  <TableCell className="font-medium">{c.company_name}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.postings_count}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.applicants}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.selected_offers}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.unique_students_placed}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </CardContent>
    </Card>
  );
}
