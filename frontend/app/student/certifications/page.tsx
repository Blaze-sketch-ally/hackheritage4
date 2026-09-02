import { redirect } from "next/navigation";
import { CertificationsView } from "@/components/student/portfolio/certifications-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentCertificationsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return <CertificationsView />;
}
