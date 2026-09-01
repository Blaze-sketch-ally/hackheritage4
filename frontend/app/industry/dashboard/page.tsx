import { DashboardView } from "@/components/industry/dashboard/dashboard-view";

// The industry layout (app/industry/layout.tsx) already guarantees an
// authenticated INDUSTRY user reaches this point. This page is a
// read-only composition over already-existing 10A-10F/Phase 9 data --
// no new backend endpoint, no new schema.
export default function IndustryDashboardPage() {
  return <DashboardView />;
}
