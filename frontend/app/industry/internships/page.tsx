import { InternshipsListView } from "@/components/industry/internships/internships-list-view";

// The industry layout already guarantees an authenticated INDUSTRY user.
// Data is loaded client-side through the FastAPI bridge
// (lib/industry/internships.ts).
export default function IndustryInternshipsPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <InternshipsListView />
    </div>
  );
}
