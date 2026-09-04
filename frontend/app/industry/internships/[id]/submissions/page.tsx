import { ProgramSubmissionsView } from "@/components/industry/internship-program/program-submissions-view";

export default async function IndustryInternshipSubmissionsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-4xl">
      <ProgramSubmissionsView internshipId={id} />
    </div>
  );
}
