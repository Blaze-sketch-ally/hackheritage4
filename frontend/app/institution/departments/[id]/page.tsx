import { DepartmentDetail } from "@/components/institution/departments/department-detail";

export default async function InstitutionDepartmentDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return (
    <div className="mx-auto max-w-4xl">
      <DepartmentDetail departmentId={id} />
    </div>
  );
}
