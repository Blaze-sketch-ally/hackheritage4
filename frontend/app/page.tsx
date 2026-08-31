import { redirect } from "next/navigation";
import { LandingNav } from "@/components/landing/landing-nav";
import { HeroSection } from "@/components/landing/hero-section";
import { WorkflowSection } from "@/components/landing/workflow-section";
import { RolesSection } from "@/components/landing/roles-section";
import { FeaturesSection } from "@/components/landing/features-section";
import { ComparisonSection } from "@/components/landing/comparison-section";
import { CtaSection } from "@/components/landing/cta-section";
import { LandingFooter } from "@/components/landing/landing-footer";
import { fetchProfileRole, getPostLoginRedirectPath } from "@/lib/auth";
import { createClient } from "@/lib/supabase/server";

export default async function HomePage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // A signed-in visitor has no reason to see the marketing page again --
  // send them straight to wherever they'd land after logging in (their
  // role's dashboard, or onboarding if they never finished it).
  if (user) {
    const role = await fetchProfileRole(supabase, user.id);
    redirect(getPostLoginRedirectPath(role));
  }

  return (
    <div className="flex flex-1 flex-col">
      <LandingNav />
      <main className="flex-1">
        <HeroSection />
        <WorkflowSection />
        <RolesSection />
        <FeaturesSection />
        <ComparisonSection />
        <CtaSection />
      </main>
      <LandingFooter />
    </div>
  );
}
