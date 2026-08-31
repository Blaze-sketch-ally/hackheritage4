import { RecruitmentApplications } from "@/components/industry/recruitment/recruitment-applications";

export default function IndustryShortlistedPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <RecruitmentApplications
        heading="Shortlisted"
        description="Candidates you've shortlisted, ready to move to interviews."
        emptyTitle="No shortlisted candidates"
        emptyDescription="Shortlist applicants from the Applicants page and they'll appear here."
        lockedStatuses={["SHORTLISTED"]}
        showTypeFilter
        layout="cards"
      />
    </div>
  );
}
