import { BarChart3, Handshake, Target, Trophy, type LucideIcon } from "lucide-react";
import { StatCard, type StatCardProps } from "@/components/dashboard/stat-card";
import type { InstitutionKpi } from "@/lib/mock/institution-dashboard";

const KPI_ICONS: Record<InstitutionKpi["id"], LucideIcon> = {
  studentsAssessed: Target,
  avgSkillScore: BarChart3,
  placementRate: Trophy,
  industryPartners: Handshake,
};

const KPI_ACCENTS: Record<InstitutionKpi["id"], NonNullable<StatCardProps["accent"]>> = {
  studentsAssessed: "indigo",
  avgSkillScore: "blue",
  placementRate: "emerald",
  industryPartners: "amber",
};

export function InstitutionKpis({ kpis }: { kpis: InstitutionKpi[] }) {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
      {kpis.map((kpi) => (
        <StatCard
          key={kpi.id}
          label={kpi.label}
          value={kpi.value}
          helperText={kpi.helperText}
          trend={kpi.trend}
          icon={KPI_ICONS[kpi.id]}
          accent={KPI_ACCENTS[kpi.id]}
        />
      ))}
    </div>
  );
}
