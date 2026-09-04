import { InternshipProgramView } from "@/components/industry/internship-program/internship-program-view";

export default async function IndustryInternshipProgramPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-3xl">
      <InternshipProgramView internshipId={id} />
    </div>
  );
}
