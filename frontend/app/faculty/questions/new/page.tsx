import { redirect } from "next/navigation";
import { CapabilityGate } from "@/components/faculty/capability-gate";
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
      <CapabilityGate capability="assessment_author" deniedMessage="Ask an Admin to grant you the Author capability to create questions.">
        <QuestionCreateForm />
      </CapabilityGate>
    </div>
  );
}
