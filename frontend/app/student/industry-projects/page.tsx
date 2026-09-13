import { IndustryProjectsListView } from "@/components/student/industry-projects/industry-projects-list-view";

export default function StudentIndustryProjectsPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Industry Projects</h1>
        <p className="text-sm text-muted-foreground">
          Practical experience working on real industry problems.
        </p>
      </div>
      <IndustryProjectsListView />
    </div>
  );
}
