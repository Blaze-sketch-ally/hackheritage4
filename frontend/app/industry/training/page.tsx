import { TrainingsListView } from "@/components/industry/training/trainings-list-view";

// The industry layout already guarantees an authenticated INDUSTRY user.
// Data is loaded client-side through the FastAPI bridge
// (lib/industry/training.ts).
export default function IndustryTrainingPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <TrainingsListView />
    </div>
  );
}
