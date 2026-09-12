import { WorkshopsListView } from "@/components/industry/workshops/workshops-list-view";

// The industry layout already guarantees an authenticated INDUSTRY user.
// Data is loaded client-side through the FastAPI bridge
// (lib/industry/workshops.ts).
export default function IndustryWorkshopsPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <WorkshopsListView />
    </div>
  );
}
