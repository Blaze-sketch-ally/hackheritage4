"use client";

import Link from "next/link";
import { Button } from "@/components/ui/button";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { ApplicationStatusActions } from "@/components/industry/applicants/application-status-actions";
import { ApplicationStatusBadge } from "@/components/industry/applicants/application-status-badge";
import { CandidateCard } from "@/components/industry/candidate-card";
import {
  OPPORTUNITY_TYPE_LABELS,
  applicantRef,
  type Application,
  type IndustrySettableStatus,
} from "@/types/application";

function formatDate(value: string | null): string {
  if (!value) return "—";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

/** Recruiter-facing applicant table. A real table on md+; stacked
 * CandidateCards below md so small screens never get a broken horizontal
 * scroll. Purely presentational — the parent owns fetching and the
 * confirm/mutation flow. */
export function ApplicantTable({
  applications,
  pendingId,
  onPick,
}: {
  applications: Application[];
  pendingId: string | null;
  onPick: (id: string, target: IndustrySettableStatus) => void;
}) {
  return (
    <>
      <div className="hidden overflow-hidden rounded-xl ring-1 ring-foreground/10 md:block">
        <Table>
          <TableHeader>
            <TableRow className="bg-muted/40 hover:bg-muted/40">
              <TableHead>Candidate</TableHead>
              <TableHead>Opportunity</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Applied on</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {applications.map((application) => (
              <TableRow key={application.id}>
                <TableCell className="font-medium">
                  <Link
                    href={`/industry/applicants/${application.id}`}
                    className="hover:underline"
                  >
                    {applicantRef(application.student_id)}
                  </Link>
                </TableCell>
                <TableCell className="max-w-[15rem] truncate">
                  {application.opportunity?.title ?? "(posting unavailable)"}
                </TableCell>
                <TableCell>{OPPORTUNITY_TYPE_LABELS[application.opportunity_type]}</TableCell>
                <TableCell>{formatDate(application.applied_at)}</TableCell>
                <TableCell>
                  <ApplicationStatusBadge status={application.status} />
                </TableCell>
                <TableCell className="text-right">
                  <div className="inline-flex flex-wrap items-center justify-end gap-1.5">
                    <Button
                      size="sm"
                      variant="ghost"
                      render={<Link href={`/industry/applicants/${application.id}`} />}
                    >
                      View
                    </Button>
                    <ApplicationStatusActions
                      status={application.status}
                      pending={pendingId === application.id}
                      onPick={(target) => onPick(application.id, target)}
                    />
                  </div>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </div>

      <div className="space-y-3 md:hidden">
        {applications.map((application) => (
          <CandidateCard
            key={application.id}
            application={application}
            pending={pendingId === application.id}
            onPick={(target) => onPick(application.id, target)}
          />
        ))}
      </div>
    </>
  );
}
