import { InternshipWorkspacesView } from "@/components/industry/internships/internship-workspaces-view";

export default async function InternshipWorkspacesPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;
  return (
    <div className="mx-auto max-w-4xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Active &amp; Completed</h1>
        <p className="text-sm text-muted-foreground">
          Students enrolled in this internship&apos;s workspace, and those who have completed it.
        </p>
      </div>
      <InternshipWorkspacesView internshipId={id} />
    </div>
  );
}
