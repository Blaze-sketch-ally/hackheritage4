import { redirect } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { Button } from "@/components/ui/button";
import { EventDetailView } from "@/components/student/events/event-detail-view";
import { createClient } from "@/lib/supabase/server";

export default async function StudentEventDetailPage({
  params,
}: {
  params: Promise<{ id: string }>;
}) {
  const supabase = await createClient();
  const {
    data: { user },
  } = await supabase.auth.getUser();
  if (!user) redirect("/login");

  const { id } = await params;

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-4">
      <Button
        variant="ghost"
        size="sm"
        className="w-fit"
        render={<Link href="/student/events" />}
        nativeButton={false}
      >
        <ArrowLeft /> Back to Events
      </Button>
      <EventDetailView eventId={id} />
    </div>
  );
}
