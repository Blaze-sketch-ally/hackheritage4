import { StudentDetailView } from "@/components/institution/students/student-detail-view";

export default async function InstitutionStudentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-4xl">
      <StudentDetailView studentId={id} />
    </div>
  );
}
