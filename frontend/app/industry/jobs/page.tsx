import { JobsListView } from "@/components/industry/jobs/jobs-list-view";

// The industry layout already guarantees an authenticated INDUSTRY user.
// Data is loaded client-side through the FastAPI bridge
// (lib/industry/jobs.ts).
export default function IndustryJobsPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <JobsListView />
    </div>
  );
}
