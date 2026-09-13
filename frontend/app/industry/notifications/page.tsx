import { redirect } from "next/navigation";
import { NotificationsView } from "@/components/industry/notifications/notifications-view";
import { createClient } from "@/lib/supabase/server";

export default async function IndustryNotificationsPage() {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();

  // The industry layout already guarantees an authenticated INDUSTRY
  // account reaches this point -- this is a defensive fallback, not a
  // second role check.
  if (!user) redirect("/login");

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Notifications</h1>
        <p className="text-sm text-muted-foreground">
          New applications and applicant activity for your postings.
        </p>
      </div>
      <NotificationsView />
    </div>
  );
}
