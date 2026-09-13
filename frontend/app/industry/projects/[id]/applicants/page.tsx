import { ProjectApplicantsView } from "@/components/industry/projects/project-applicants-view";

export default async function ProjectApplicantsPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Applicants</h1>
        <p className="text-sm text-muted-foreground">Students who applied to this project.</p>
      </div>
      <ProjectApplicantsView projectId={id} />
    </div>
  );
}
