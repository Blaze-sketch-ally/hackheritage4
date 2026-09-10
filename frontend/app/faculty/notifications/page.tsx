import { redirect } from "next/navigation";
import { NotificationsView } from "@/components/faculty/notifications/notifications-view";
import { createClient } from "@/lib/supabase/server";

export default async function FacultyNotificationsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The faculty layout already guarantees an authenticated FACULTY reaches
  // this point — this is a defensive fallback, not a second role check.
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Notifications</h1>
        <p className="text-sm text-muted-foreground">
          Evaluation assignments, review decisions, and mentorship updates.
        </p>
      </div>
      <NotificationsView />
    </div>
  );
}
