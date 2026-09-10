"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { createMentorshipOpportunity } from "@/lib/industry/mentorship-opportunities";
import { ApiError } from "@/lib/api";
import { MentorshipForm } from "@/components/industry/mentorship/mentorship-form";
import type { MentorshipCreate } from "@/types/industry-mentorship";

export function MentorshipCreateView() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(data: MentorshipCreate) {
    setSubmitting(true);
    setError(null);
    try {
      const created = await createMentorshipOpportunity(data);
      router.push(`/industry/mentorship/${created.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not create the mentorship opportunity. Please try again.",
      );
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Link
          href="/industry/mentorship"
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> All mentorship opportunities
        </Link>
        <div>
          <h1 className="text-xl font-semibold">Create Mentorship Opportunity</h1>
          <p className="text-sm text-muted-foreground">
            Saved as a draft. You can review and publish it afterwards.
          </p>
        </div>
      </div>

      <MentorshipForm
        mode="create"
        submitting={submitting}
        error={error}
        onSubmit={handleSubmit}
        onCancel={() => router.push("/industry/mentorship")}
      />
    </div>
  );
}
