import { redirect } from "next/navigation";
import { PortfolioView } from "@/components/portfolio/portfolio-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentPortfolioPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Portfolio</h1>
        <p className="text-sm text-muted-foreground">
          Showcase real work and credentials. Industry reviewers see this alongside your skill match once you apply.
        </p>
      </div>
      <PortfolioView />
    </div>
  );
}
