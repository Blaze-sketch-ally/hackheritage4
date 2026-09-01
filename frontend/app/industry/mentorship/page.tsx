import { MentorshipListView } from "@/components/industry/mentorship/mentorship-list-view";

// The industry layout already guarantees an authenticated INDUSTRY user.
// Data is loaded client-side through the FastAPI bridge
// (lib/industry/mentorship-opportunities.ts).
export default function IndustryMentorshipPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <MentorshipListView />
    </div>
  );
}
