import { WorkshopsListView } from "@/components/student/workshops/workshops-list-view";

export default function StudentWorkshopsPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Workshops</h1>
        <p className="text-sm text-muted-foreground">
          Industry exposure and learning sessions offered by companies.
        </p>
      </div>
      <WorkshopsListView />
    </div>
  );
}
