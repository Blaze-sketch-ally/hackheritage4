import { redirect } from "next/navigation";

// This route previously had zero real content. Rather than building a
// fourth near-duplicate opportunity view (list, edit, applicants, and
// this), it redirects to the canonical management page for one
// opportunity -- applicants is the most useful destination for an
// industry user clicking into one of their own postings. Editing is one
// click away from there.
export default async function IndustryInternshipRedirectPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  redirect(`/industry/opportunities/${id}/applicants`);
}
