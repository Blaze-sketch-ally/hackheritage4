import { AnalyticsView } from "@/components/industry/analytics/analytics-view";

// The industry layout (app/industry/layout.tsx) already guarantees an
// authenticated INDUSTRY user reaches this point. Every metric is
// computed server-side from this account's own records via the single
// GET /api/v1/analytics/industry aggregation endpoint — no analytics
// table, no fabricated history.
export default function IndustryAnalyticsPage() {
  return <AnalyticsView />;
}
