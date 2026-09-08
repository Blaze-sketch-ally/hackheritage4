import { redirect } from "next/navigation";
import { MyInstitutionView } from "@/components/student/institution/my-institution-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentInstitutionPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The student layout already guarantees an authenticated STUDENT reaches
  // this point — this is a defensive fallback, not a second role check.
  if (!user) redirect("/login");

  return <MyInstitutionView />;
}
