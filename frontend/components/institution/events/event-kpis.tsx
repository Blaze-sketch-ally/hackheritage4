import { Building2, CalendarCheck, CalendarClock, CalendarDays, Handshake } from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
import type { EventKpis as EventKpisType } from "@/types/institution-event";

/** Core KPIs (Phase 10, Part 15) -- counts the union of institution-
 * organized events and platform-wide published Industry workshops.
 * Never a registration/attendance number (none is modeled). */
export function EventKpis({ kpis }: { kpis: EventKpisType }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-6">
      <StatCard label="Total Events" value={kpis.total_events.toLocaleString()} icon={CalendarDays} accent="indigo" />
      <StatCard label="Upcoming" value={kpis.upcoming_events.toLocaleString()} icon={CalendarClock} accent="blue" />
      <StatCard label="Ongoing" value={kpis.ongoing_events.toLocaleString()} icon={CalendarClock} accent="violet" />
      <StatCard label="Completed" value={kpis.completed_events.toLocaleString()} icon={CalendarCheck} accent="emerald" />
      <StatCard label="Industry Events" value={kpis.industry_events.toLocaleString()} icon={Handshake} accent="amber" />
      <StatCard label="Institution-Organized" value={kpis.institution_organized_events.toLocaleString()} icon={Building2} accent="indigo" />
    </div>
  );
}
