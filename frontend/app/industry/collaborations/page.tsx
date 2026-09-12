import { CollaborationsListView } from "@/components/industry/collaborations/collaborations-list-view";

// The industry layout already guarantees an authenticated INDUSTRY user.
// Data is loaded client-side through the FastAPI bridge
// (lib/industry/collaborations.ts).
export default function IndustryCollaborationsPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <CollaborationsListView />
    </div>
  );
}
