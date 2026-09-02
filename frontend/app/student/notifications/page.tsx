import { redirect } from "next/navigation";
import { NotificationsView } from "@/components/student/notifications/notifications-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentNotificationsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The student layout already guarantees an authenticated STUDENT reaches
  // this point — this is a defensive fallback, not a second role check.
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Notifications</h1>
        <p className="text-sm text-muted-foreground">
          Updates about your applications, assessments, learning, events, and mentorship.
        </p>
      </div>
      <NotificationsView />
    </div>
  );
}
