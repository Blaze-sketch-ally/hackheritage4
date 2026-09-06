import { redirect } from "next/navigation";
import { LearningBrowseView } from "@/components/student/learning/learning-browse-view";
import { LearningRecommendations } from "@/components/student/learning/learning-recommendations";
import { createClient } from "@/lib/supabase/server";

export default async function StudentLearningPage() {
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
        <h1 className="text-xl font-semibold">Learning &amp; Courses</h1>
        <p className="text-sm text-muted-foreground">
          A curated catalog of courses, articles, and videos, each mapped to the skills it builds.
          Save what you want to come back to, and track what you&apos;re working through.
        </p>
      </div>
      <LearningRecommendations />
      <LearningBrowseView />
    </div>
  );
}
