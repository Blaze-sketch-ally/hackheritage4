import { ParticipantsView } from "@/components/industry/participants/participants-view";

export default function IndustryParticipantsPage() {
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">All Participants</h1>
        <p className="text-sm text-muted-foreground">
          Every student who applied, was selected, or enrolled across your Jobs, Internships,
          Projects, Workshops, and Training.
        </p>
      </div>
      <ParticipantsView />
    </div>
  );
}
