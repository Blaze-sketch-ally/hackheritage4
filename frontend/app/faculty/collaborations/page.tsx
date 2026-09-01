import { RecipientCollaborationsView } from "@/components/collaborations/recipient-collaborations-view";

// frontend/app/faculty/layout.tsx now gates this route to role === "FACULTY".
// Data is loaded client-side through the FastAPI bridge
// (lib/industry/collaborations.ts) -- the incoming-collaborations
// endpoints are shared with the Industry side, scoped server-side by the
// caller's own identity.
export default function FacultyCollaborationsPage() {
  return <RecipientCollaborationsView heading="Collaborations" />;
}
