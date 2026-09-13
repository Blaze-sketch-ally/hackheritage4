import { TrainingsListView } from "@/components/student/training/trainings-list-view";

export default function StudentTrainingsPage() {
  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Training</h1>
        <p className="text-sm text-muted-foreground">
          Upskilling programs offered by companies.
        </p>
      </div>
      <TrainingsListView />
    </div>
  );
}
