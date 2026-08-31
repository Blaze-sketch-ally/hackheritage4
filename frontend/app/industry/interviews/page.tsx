import { RecruitmentApplications } from "@/components/industry/recruitment/recruitment-applications";

// Interview-stage candidates only. There is no interview date/time/location
// field in the schema (migration 020), so this is a filtered candidate
// list — not a scheduling system.
export default function IndustryInterviewsPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <RecruitmentApplications
        heading="Interviews"
        description="Candidates at the interview stage of your recruitment pipeline."
        emptyTitle="No candidates at the interview stage"
        emptyDescription="Move shortlisted candidates to “Schedule interview” and they'll appear here."
        lockedStatuses={["INTERVIEW_SCHEDULED"]}
        showTypeFilter
        layout="cards"
      />
    </div>
  );
}
