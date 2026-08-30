import { redirect } from "next/navigation";
import { QuestionDetailView } from "@/components/faculty/question-detail-view";
import { createClient } from "@/lib/supabase/server";

export default async function FacultyQuestionDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const { id } = await params;

  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <div className="mx-auto max-w-2xl">
      <QuestionDetailView questionId={id} />
    </div>
  );
}
