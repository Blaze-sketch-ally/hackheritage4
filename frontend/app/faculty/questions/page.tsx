import { redirect } from "next/navigation";
import { QuestionBankView } from "@/components/faculty/question-bank-view";
import { createClient } from "@/lib/supabase/server";

export default async function FacultyQuestionsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The faculty layout already guarantees an authenticated FACULTY reaches
  // this point — this is a defensive fallback, not a second role check.
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-5xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Question bank</h1>
        <p className="text-sm text-muted-foreground">
          Author questions and review submissions from other setters.
        </p>
      </div>
      <QuestionBankView />
    </div>
  );
}
