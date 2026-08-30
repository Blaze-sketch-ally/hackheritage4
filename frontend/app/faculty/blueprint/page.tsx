import { redirect } from "next/navigation";
import { BlueprintEditor } from "@/components/faculty/blueprint-editor";
import { createClient } from "@/lib/supabase/server";

export default async function FacultyBlueprintPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-2xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Assessment blueprints</h1>
        <p className="text-sm text-muted-foreground">
          Configure how many questions of each difficulty a student&apos;s attempt randomly draws.
        </p>
      </div>
      <BlueprintEditor />
    </div>
  );
}
