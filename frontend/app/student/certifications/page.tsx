import { redirect } from "next/navigation";
import { PortfolioView } from "@/components/portfolio/portfolio-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentCertificationsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Certifications</h1>
        <p className="text-sm text-muted-foreground">Credentials that strengthen your professional profile.</p>
      </div>
      <PortfolioView section="certifications" />
    </div>
  );
}
