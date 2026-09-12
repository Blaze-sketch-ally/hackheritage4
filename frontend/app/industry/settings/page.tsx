import { IndustrySettingsView } from "@/components/industry/settings/industry-settings-view";

// The industry layout (app/industry/layout.tsx) already guarantees an
// authenticated INDUSTRY user reaches this point. Account data is loaded
// client-side directly via Supabase (lib/profile.ts) -- the same
// architecture boundary auth/profile data has always used in this
// project, not routed through the FastAPI backend.
export default function IndustrySettingsPage() {
  return <IndustrySettingsView />;
}
