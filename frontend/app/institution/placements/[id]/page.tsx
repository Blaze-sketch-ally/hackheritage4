import { PlacementDriveDetail } from "@/components/institution/placements/placement-drive-detail";

export default async function InstitutionPlacementDrivePage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  return <PlacementDriveDetail driveId={id} />;
}
