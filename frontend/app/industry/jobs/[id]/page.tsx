import { redirect } from "next/navigation";

// Same reasoning as app/industry/internships/[id]/page.tsx.
export default async function IndustryJobRedirectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/industry/opportunities/${id}/applicants`);
}
