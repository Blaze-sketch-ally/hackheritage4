import { InterviewDetailView } from "@/components/industry/interviews/interview-detail-view";

export default async function IndustryInterviewDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-3xl">
      <InterviewDetailView interviewId={id} />
    </div>
  );
}
