import { MentorshipDetailView } from "@/components/industry/mentorship/mentorship-detail-view";

export default async function IndustryMentorshipDetailPage({
  params,
  searchParams,
}: {
  params: Promise<{ id: string }>;
  searchParams: Promise<{ edit?: string | string[] }>;
}) {
  const { id } = await params;
  const sp = await searchParams;

  return (
    <div className="mx-auto max-w-3xl">
      <MentorshipDetailView mentorshipId={id} initialEdit={sp.edit === "1"} />
    </div>
  );
}
