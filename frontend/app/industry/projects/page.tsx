import { ProjectsListView } from "@/components/industry/projects/projects-list-view";

// The industry layout already guarantees an authenticated INDUSTRY user.
// Data is loaded client-side through the FastAPI bridge
// (lib/industry/projects.ts).
export default function IndustryProjectsPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <ProjectsListView />
    </div>
  );
}
