import { redirect } from "next/navigation";
import { PortfolioView } from "@/components/portfolio/portfolio-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentAchievementsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Achievements</h1>
        <p className="text-sm text-muted-foreground">Awards, recognitions, and milestones worth highlighting.</p>
      </div>
      <PortfolioView section="achievements" />
    </div>
  );
}
