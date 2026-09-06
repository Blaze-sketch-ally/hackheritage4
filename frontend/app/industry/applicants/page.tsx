import { RecruitmentApplications } from "@/components/industry/recruitment/recruitment-applications";

// The industry layout already guarantees an authenticated INDUSTRY user.
// Data is loaded client-side through the FastAPI bridge
// (lib/industry/applications.ts).
export default function IndustryApplicantsPage() {
  return (
    <div className="mx-auto max-w-5xl">
      <RecruitmentApplications
        heading="Applicants"
        description="Every application submitted to your internships and jobs."
        emptyTitle="No applications yet"
        emptyDescription="When students apply to your published internships and jobs, they'll appear here."
        showFunnel
        showStatusFilter
        showTypeFilter
        layout="table"
      />
    </div>
  );
}
