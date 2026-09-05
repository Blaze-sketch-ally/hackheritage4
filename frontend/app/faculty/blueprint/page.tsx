import Link from "next/link";
import { redirect } from "next/navigation";
import { BlueprintEditor } from "@/components/faculty/blueprint-editor";
import { CapabilityGate } from "@/components/faculty/capability-gate";
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
        <Link href="/faculty/assessment-studio" className="text-xs text-muted-foreground hover:underline">
          ← Question Studio
        </Link>
        <h1 className="text-xl font-semibold">Assessment blueprints</h1>
        <p className="text-sm text-muted-foreground">
          Configure how many questions of each difficulty a student&apos;s attempt randomly draws.
        </p>
      </div>
      <CapabilityGate
        capability="assessment_author"
        deniedMessage="Ask an Admin to grant you the Author capability to manage assessment blueprints."
      >
        <BlueprintEditor />
      </CapabilityGate>
    </div>
  );
}
