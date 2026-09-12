import { RecruitmentApplications } from "@/components/industry/recruitment/recruitment-applications";

export default function IndustrySelectedPage() {
  return (
    <div className="mx-auto max-w-4xl">
      <RecruitmentApplications
        heading="Selected"
        description="Candidates you've selected from your internships and jobs."
        emptyTitle="No selected candidates yet"
        emptyDescription="Candidates you mark as selected after interviews will appear here."
        lockedStatuses={["SELECTED"]}
        showTypeFilter
        layout="cards"
      />
    </div>
  );
}
