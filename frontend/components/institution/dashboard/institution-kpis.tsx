import { Briefcase, GraduationCap, TrendingUp, Users } from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
import type { InstitutionOverview } from "@/types/institution-analytics";

export function InstitutionKpis({ overview }: { overview: InstitutionOverview }) {
  const { student_metrics: sm, opportunities } = overview;

  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <StatCard
        label="Students"
        value={sm.total_linked_students.toLocaleString()}
        helperText="linked to your institution"
        icon={Users}
        accent="indigo"
      />
      <StatCard
        label="Placed"
        value={sm.placed.toLocaleString()}
        helperText="at least one offer accepted"
        icon={GraduationCap}
        accent="emerald"
      />
      <StatCard
        label="Unplaced"
        value={sm.unplaced_active.toLocaleString()}
        helperText="applying, no offer yet"
        icon={Users}
        accent="amber"
      />
      <StatCard
        label="Placement Rate"
        value={sm.placement_percentage != null ? `${sm.placement_percentage}%` : "—"}
        helperText={sm.total_linked_students === 0 ? "no linked students yet" : "of linked students"}
        icon={TrendingUp}
        accent="violet"
      />
      <StatCard
        label="Active Jobs"
        value={opportunities.active_jobs.toLocaleString()}
        helperText="published, platform-wide"
        icon={Briefcase}
        accent="blue"
      />
      <StatCard
        label="Active Internships"
        value={opportunities.active_internships.toLocaleString()}
        helperText="published, platform-wide"
        icon={Briefcase}
        accent="blue"
      />
    </div>
  );
}
