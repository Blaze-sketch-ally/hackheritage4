import { InterviewsListView } from "@/components/industry/interviews/interviews-list-view";

// The industry layout (app/industry/layout.tsx) already guarantees an
// authenticated INDUSTRY user reaches this point. Previously this route
// was only a filtered candidate list (applications.status =
// 'INTERVIEW_SCHEDULED'); it is now the real interview scheduler backed
// by the `interviews` table (migration 030) and /api/v1/interviews.
export default function IndustryInterviewsPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <InterviewsListView />
    </div>
  );
}
