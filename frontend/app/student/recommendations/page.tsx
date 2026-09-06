import { redirect } from "next/navigation";
import { RecommendationsView } from "@/components/student/recommendations/recommendations-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentRecommendationsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The student layout already guarantees an authenticated STUDENT reaches
  // this point — this is a defensive fallback, not a second role check.
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Recommended for you</h1>
        <p className="text-sm text-muted-foreground">
          Existing opportunities and learning resources, ranked by how well they match your
          canonical skills and target role.
        </p>
      </div>
      <RecommendationsView />
    </div>
  );
}
