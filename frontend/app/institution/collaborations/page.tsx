import { InstitutionCollaborationsView } from "@/components/institution/collaborations/institution-collaborations-view";

// frontend/app/institution/layout.tsx gates this route to
// role === "INSTITUTION". Data is loaded client-side through the FastAPI
// bridge (lib/industry/collaborations.ts) -- the incoming-collaborations
// endpoints are shared with the Industry side, scoped server-side by the
// caller's own identity. Unlike Faculty (which still uses the shared,
// minimal RecipientCollaborationsView), Institution gets its own richer
// view (sections, search, filter, a detail route) on top of the exact
// same underlying API -- see InstitutionCollaborationsView's own
// docstring.
export default function InstitutionCollaborationsPage() {
  return <InstitutionCollaborationsView />;
}
