import { Info } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { StatCard } from "@/components/dashboard/stat-card";
import type { InstitutionReportResponse } from "@/types/institution-reports";

function pct(value: number | null): string {
  return value != null ? `${value}%` : "N/A";
}

function Note({ text }: { text: string }) {
  return (
    <p className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground">
      <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
      {text}
    </p>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}

/** Renders whichever single report section is populated on `report`
 * (Phase 11) -- report-specific tables/summaries only, reusing the same
 * design-system primitives as every other institution page. */
export function ReportOutput({ report }: { report: InstitutionReportResponse }) {
  switch (report.report_type) {
    case "PLACEMENT":
      return report.placement ? <PlacementReportOutput data={report.placement} /> : null;
    case "INTERNSHIP":
      return report.internship ? <InternshipReportOutput data={report.internship} /> : null;
    case "STUDENT":
      return report.student ? <StudentReportOutput data={report.student} /> : null;
    case "DEPARTMENT":
      return report.department ? <DepartmentReportOutput data={report.department} /> : null;
    case "INDUSTRY":
      return report.industry ? <CompanyReportOutput data={report.industry} /> : null;
    case "EVENTS":
      return report.events ? <EventsReportOutput data={report.events} /> : null;
    case "COLLABORATION":
      return report.collaboration ? <CollaborationReportOutput data={report.collaboration} /> : null;
    default:
      return null;
  }
}

function PlacementReportOutput({ data }: { data: NonNullable<InstitutionReportResponse["placement"]> }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="Total Students" value={String(data.summary.total_students)} icon={Info} accent="indigo" />
        <StatCard label="With Applications" value={String(data.summary.students_with_applications)} icon={Info} accent="blue" />
        <StatCard label="Selected" value={String(data.summary.students_selected)} icon={Info} accent="emerald" />
        <StatCard label="Placement Rate" value={pct(data.summary.placement_rate)} icon={Info} accent="violet" />
        <StatCard label="Companies Involved" value={String(data.summary.companies_involved)} icon={Info} accent="amber" />
        <StatCard label="Active Drives" value={String(data.summary.active_placement_drives)} icon={Info} accent="indigo" />
      </div>

      <Section title="Department Breakdown">
        {data.department_breakdown.length === 0 ? (
          <p className="text-sm text-muted-foreground/70">No department data.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Department</TableHead>
                <TableHead className="text-right">Students</TableHead>
                <TableHead className="text-right">Selected</TableHead>
                <TableHead className="text-right">Placement Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.department_breakdown.map((d) => (
                <TableRow key={d.department_id}>
                  <TableCell className="font-medium">{d.department}</TableCell>
                  <TableCell className="text-right tabular-nums">{d.student_count}</TableCell>
                  <TableCell className="text-right tabular-nums">{d.placed_count}</TableCell>
                  <TableCell className="text-right tabular-nums">{d.student_count === 0 ? "N/A" : pct(d.placement_rate)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Section>

      <Section title="Company Breakdown">
        {data.company_breakdown.length === 0 ? (
          <p className="text-sm text-muted-foreground/70">No company activity.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead className="text-right">Applicants</TableHead>
                <TableHead className="text-right">Selected Offers</TableHead>
                <TableHead className="text-right">Unique Students Placed</TableHead>
                <TableHead className="text-right">Selection Rate</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.company_breakdown.map((c) => (
                <TableRow key={c.company_name}>
                  <TableCell className="font-medium">{c.company_name}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.applicants}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.selected_offers}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.unique_students_placed}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.applicants === 0 ? "N/A" : pct(c.selection_rate)}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Section>

      <Section title="Application Status Breakdown">
        <ul className="space-y-1.5">
          {data.status_breakdown.map((s) => (
            <li key={s.label} className="flex items-center justify-between text-sm">
              <span>{s.label}</span>
              <span className="font-semibold tabular-nums">{s.count}</span>
            </li>
          ))}
        </ul>
      </Section>

      <Note text={data.note} />
    </div>
  );
}

function InternshipReportOutput({ data }: { data: NonNullable<InstitutionReportResponse["internship"]> }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        <StatCard label="Selected Internships" value={String(data.kpis.curated_internships)} icon={Info} accent="indigo" />
        <StatCard label="Active Internships" value={String(data.kpis.active_internships)} icon={Info} accent="blue" />
        <StatCard label="Companies" value={String(data.kpis.companies)} icon={Info} accent="violet" />
        <StatCard label="Applicants" value={String(data.kpis.applicants)} icon={Info} accent="amber" />
        <StatCard label="Selected Students" value={String(data.kpis.selected_students)} icon={Info} accent="emerald" />
        <StatCard label="Active Participants" value={String(data.kpis.active_participants)} icon={Info} accent="violet" />
        <StatCard label="Completed" value={String(data.kpis.completed_internships)} icon={Info} accent="emerald" />
      </div>

      <Section title="Department Distribution">
        {data.department_breakdown.length === 0 ? (
          <p className="text-sm text-muted-foreground/70">No department data.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Department</TableHead>
                <TableHead className="text-right">Participants</TableHead>
                <TableHead className="text-right">Selected</TableHead>
                <TableHead className="text-right">Completed</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.department_breakdown.map((d) => (
                <TableRow key={d.department_id}>
                  <TableCell className="font-medium">{d.department}</TableCell>
                  <TableCell className="text-right tabular-nums">{d.participants}</TableCell>
                  <TableCell className="text-right tabular-nums">{d.selected_count}</TableCell>
                  <TableCell className="text-right tabular-nums">{d.completed_count}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Section>

      <Section title="Company Breakdown">
        {data.company_breakdown.length === 0 ? (
          <p className="text-sm text-muted-foreground/70">No company activity.</p>
        ) : (
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Company</TableHead>
                <TableHead className="text-right">Opportunities</TableHead>
                <TableHead className="text-right">Applicants</TableHead>
                <TableHead className="text-right">Selected</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {data.company_breakdown.map((c) => (
                <TableRow key={c.company_name}>
                  <TableCell className="font-medium">{c.company_name}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.opportunities}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.applicants}</TableCell>
                  <TableCell className="text-right tabular-nums">{c.selected}</TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        )}
      </Section>

      <Section title="Stipend by Currency">
        {data.stipend_by_currency.length === 0 ? (
          <p className="text-sm text-muted-foreground/70">No stipend data available.</p>
        ) : (
          <ul className="space-y-1.5 text-sm">
            {data.stipend_by_currency.map((row) => (
              <li key={row.currency}>
                <span className="font-medium">{row.currency}</span> — {row.internship_count} internships, avg{" "}
                {row.average_stipend.toLocaleString()}, min {row.min_stipend.toLocaleString()}, max {row.max_stipend.toLocaleString()}
              </li>
            ))}
          </ul>
        )}
      </Section>

      <Note text={data.note} />
    </div>
  );
}

function StudentReportOutput({ data }: { data: NonNullable<InstitutionReportResponse["student"]> }) {
  return (
    <div className="space-y-6">
      <p className="text-sm text-muted-foreground">
        Showing {data.students.length} of {data.total} students (page {data.page}).
      </p>
      {data.students.length === 0 ? (
        <p className="text-sm text-muted-foreground/70">No students match these filters.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Name</TableHead>
              <TableHead>Department</TableHead>
              <TableHead className="text-right">Batch</TableHead>
              <TableHead className="text-right">CGPA</TableHead>
              <TableHead>Placement</TableHead>
              <TableHead>Internship</TableHead>
              <TableHead>Top Skills</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.students.map((s, i) => (
              <TableRow key={`${s.username ?? s.full_name}-${i}`}>
                <TableCell className="font-medium">{s.full_name ?? s.username ?? "Unknown"}</TableCell>
                <TableCell className="text-muted-foreground">{s.department}</TableCell>
                <TableCell className="text-right tabular-nums">{s.batch ?? "—"}</TableCell>
                <TableCell className="text-right tabular-nums">{s.cgpa ?? "—"}</TableCell>
                <TableCell>{s.placement_status}</TableCell>
                <TableCell>{s.internship_status}</TableCell>
                <TableCell className="text-muted-foreground">{s.top_skills.join(", ") || "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Note text={data.note} />
    </div>
  );
}

function DepartmentReportOutput({ data }: { data: NonNullable<InstitutionReportResponse["department"]> }) {
  return (
    <div className="space-y-6">
      {data.departments.length === 0 ? (
        <p className="text-sm text-muted-foreground/70">No departments set up yet.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Department</TableHead>
              <TableHead className="text-right">Students</TableHead>
              <TableHead className="text-right">Avg CGPA</TableHead>
              <TableHead className="text-right">Placed</TableHead>
              <TableHead className="text-right">Placement Rate</TableHead>
              <TableHead className="text-right">Internship Selected</TableHead>
              <TableHead className="text-right">Applications</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.departments.map((d) => (
              <TableRow key={d.id}>
                <TableCell className="font-medium">
                  {d.name}
                  {d.code ? <span className="ml-1 text-xs text-muted-foreground">({d.code})</span> : null}
                </TableCell>
                <TableCell className="text-right tabular-nums">{d.student_count}</TableCell>
                <TableCell className="text-right tabular-nums">{d.average_cgpa ?? "N/A"}</TableCell>
                <TableCell className="text-right tabular-nums">{d.placed_count}</TableCell>
                <TableCell className="text-right tabular-nums">{d.student_count === 0 ? "N/A" : pct(d.placement_rate)}</TableCell>
                <TableCell className="text-right tabular-nums">{d.internship_selected_count}</TableCell>
                <TableCell className="text-right tabular-nums">{d.applications_total}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Note text={data.note} />
    </div>
  );
}

function CompanyReportOutput({ data }: { data: NonNullable<InstitutionReportResponse["industry"]> }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Total Partners" value={String(data.metrics.total_partners)} icon={Info} accent="indigo" />
        <StatCard label="Active Partners" value={String(data.metrics.active_partners)} icon={Info} accent="emerald" />
        <StatCard label="Recruiting" value={String(data.metrics.recruiting_partners)} icon={Info} accent="blue" />
        <StatCard label="Internship Partners" value={String(data.metrics.internship_partners)} icon={Info} accent="violet" />
      </div>

      {data.companies.length === 0 ? (
        <p className="text-sm text-muted-foreground/70">No companies match these filters.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Company</TableHead>
              <TableHead>Relationship</TableHead>
              <TableHead className="text-right">Jobs</TableHead>
              <TableHead className="text-right">Internships</TableHead>
              <TableHead className="text-right">Drives</TableHead>
              <TableHead className="text-right">Students Selected</TableHead>
              <TableHead className="text-right">Connections</TableHead>
              <TableHead className="text-right">Events</TableHead>
              <TableHead className="text-right">Collaborations</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.companies.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="font-medium">{c.company_name ?? "Unknown company"}</TableCell>
                <TableCell>
                  {c.relationship_status ? (
                    <Badge variant="outline">{c.relationship_status}</Badge>
                  ) : (
                    <span className="text-xs text-muted-foreground">Not tracked</span>
                  )}
                </TableCell>
                <TableCell className="text-right tabular-nums">{c.jobs_opportunities}</TableCell>
                <TableCell className="text-right tabular-nums">{c.internship_opportunities}</TableCell>
                <TableCell className="text-right tabular-nums">{c.placement_drives_count}</TableCell>
                <TableCell className="text-right tabular-nums">{c.students_selected}</TableCell>
                <TableCell className="text-right tabular-nums">{c.connections_count}</TableCell>
                <TableCell className="text-right tabular-nums">{c.events_count}</TableCell>
                <TableCell className="text-right tabular-nums">{c.collaborations_count}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Note text={data.note} />
    </div>
  );
}

function EventsReportOutput({ data }: { data: NonNullable<InstitutionReportResponse["events"]> }) {
  return (
    <div className="space-y-6">
      <div className="grid gap-3 sm:grid-cols-3">
        <StatCard label="Total Events" value={String(data.total_events)} icon={Info} accent="indigo" />
        <StatCard label="Upcoming" value={String(data.upcoming_events)} icon={Info} accent="blue" />
        <StatCard label="Completed" value={String(data.completed_events)} icon={Info} accent="emerald" />
      </div>

      {data.events.length === 0 ? (
        <p className="text-sm text-muted-foreground/70">No events match these filters.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Event</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Departments</TableHead>
              <TableHead>Source</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.events.map((e) => (
              <TableRow key={`${e.source}-${e.id}`}>
                <TableCell className="font-medium">{e.title}</TableCell>
                <TableCell className="text-muted-foreground">{e.event_type}</TableCell>
                <TableCell className="text-muted-foreground">{e.company_name ?? "—"}</TableCell>
                <TableCell>
                  <Badge variant="outline">{e.status}</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">
                  {e.target_department_names.length > 0 ? e.target_department_names.join(", ") : "All"}
                </TableCell>
                <TableCell className="text-xs text-muted-foreground">{e.platform_wide ? "Industry-hosted" : "Institution"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Note text={data.registration_note} />
    </div>
  );
}

function CollaborationReportOutput({ data }: { data: NonNullable<InstitutionReportResponse["collaboration"]> }) {
  return (
    <div className="space-y-6">
      <Section title="Status Breakdown">
        <ul className="space-y-1.5">
          {data.status_breakdown.map((s) => (
            <li key={s.label} className="flex items-center justify-between text-sm">
              <span>{s.label}</span>
              <span className="font-semibold tabular-nums">{s.count}</span>
            </li>
          ))}
        </ul>
      </Section>

      {data.collaborations.length === 0 ? (
        <p className="text-sm text-muted-foreground/70">No collaborations match these filters.</p>
      ) : (
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Title</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Created</TableHead>
              <TableHead>Updated</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {data.collaborations.map((c) => (
              <TableRow key={c.id}>
                <TableCell className="font-medium">{c.title}</TableCell>
                <TableCell className="text-muted-foreground">{c.company_name ?? "—"}</TableCell>
                <TableCell>
                  <Badge variant="outline">{c.status}</Badge>
                </TableCell>
                <TableCell className="text-muted-foreground">{c.created_at?.slice(0, 10) ?? "—"}</TableCell>
                <TableCell className="text-muted-foreground">{c.updated_at?.slice(0, 10) ?? "—"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      )}
      <Note text={data.note} />
    </div>
  );
}
