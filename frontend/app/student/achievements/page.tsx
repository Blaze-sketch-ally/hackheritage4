import { redirect } from "next/navigation";
import { AchievementsView } from "@/components/student/portfolio/achievements-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentAchievementsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return <AchievementsView />;
}
