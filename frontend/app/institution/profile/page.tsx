import { InstitutionProfileView } from "@/components/institution/profile/institution-profile-view";

// The institution layout (app/institution/layout.tsx) already guarantees
// an authenticated INSTITUTION user reaches this point. The profile
// itself is loaded client-side through the FastAPI bridge
// (lib/institution/profile.ts), the same pattern as /industry/profile.
export default function InstitutionProfilePage() {
  return (
    <div className="mx-auto max-w-3xl">
      <InstitutionProfileView />
    </div>
  );
}
