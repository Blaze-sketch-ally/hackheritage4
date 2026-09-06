import { Briefcase, Building2, CheckCircle2, GraduationCap, UserCheck, Users } from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
import type { InternshipKpis as InternshipKpisType } from "@/types/institution-internship";

/**
 * Core KPIs over this institution's CURATED internship list only.
 * `curated_internships` is the total this institution has selected;
 * `active_internships` is the narrower subset of those still PUBLISHED by
 * their company -- a DIFFERENT, smaller number than the Institution
 * Dashboard's platform-wide "Active Internships" card (which counts every
 * PUBLISHED internship on the platform, not this institution's curated
 * set). `completed_internships` counts completed PARTICIPATIONS (a
 * student can complete more than one internship), distinct from unique
 * students -- see `active_participants`.
 */
export function InternshipKpis({ kpis }: { kpis: InternshipKpisType }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <StatCard
        label="Selected Internships"
        value={kpis.curated_internships.toLocaleString()}
        helperText="curated by your institution"
        icon={Briefcase}
        accent="indigo"
      />
      <StatCard
        label="Active Internships"
        value={kpis.active_internships.toLocaleString()}
        helperText="curated & still published"
        icon={CheckCircle2}
        accent="blue"
      />
      <StatCard
        label="Companies"
        value={kpis.companies.toLocaleString()}
        helperText="represented"
        icon={Building2}
        accent="violet"
      />
      <StatCard
        label="Applicants"
        value={kpis.applicants.toLocaleString()}
        helperText="unique students"
        icon={Users}
        accent="amber"
      />
      <StatCard
        label="Selected Students"
        value={kpis.selected_students.toLocaleString()}
        helperText="unique students"
        icon={UserCheck}
        accent="emerald"
      />
      <StatCard
        label="Completed Internships"
        value={kpis.completed_internships.toLocaleString()}
        helperText={kpis.participation_unknown > 0 ? `${kpis.participation_unknown} unknown` : "estimated"}
        icon={GraduationCap}
        accent="emerald"
      />
    </div>
  );
}
