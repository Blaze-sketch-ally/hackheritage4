import { redirect } from "next/navigation";
import { QuestionCreateForm } from "@/components/faculty/question-create-form";
import { createClient } from "@/lib/supabase/server";

export default async function FacultyNewQuestionPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <div className="mx-auto max-w-2xl">
      <QuestionCreateForm />
    </div>
  );
}
