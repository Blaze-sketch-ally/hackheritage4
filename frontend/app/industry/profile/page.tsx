import { IndustryProfileView } from "@/components/industry/profile/industry-profile-view";

// The industry layout (app/industry/layout.tsx) already guarantees an
// authenticated INDUSTRY user reaches this point. The company profile
// itself is loaded client-side through the FastAPI bridge
// (lib/industry/profile.ts), the same pattern as /student/skill-gap.
export default function IndustryProfilePage() {
  return (
    <div className="mx-auto max-w-3xl">
      <IndustryProfileView />
    </div>
  );
}
