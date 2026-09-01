"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { createCollaboration } from "@/lib/industry/collaborations";
import { ApiError } from "@/lib/api";
import { CollaborationForm } from "@/components/industry/collaborations/collaboration-form";
import type { CollaborationCreate } from "@/types/industry-collaboration";

export function CollaborationCreateView() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(data: CollaborationCreate) {
    setSubmitting(true);
    setError(null);
    try {
      const created = await createCollaboration(data);
      router.push(`/industry/collaborations/${created.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not create the collaboration. Please try again.",
      );
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Link
          href="/industry/collaborations"
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> All collaborations
        </Link>
        <div>
          <h1 className="text-xl font-semibold">Create Collaboration</h1>
          <p className="text-sm text-muted-foreground">
            Saved as a draft. You can review and send it afterwards.
          </p>
        </div>
      </div>

      <CollaborationForm
        mode="create"
        submitting={submitting}
        error={error}
        onSubmit={handleSubmit}
        onCancel={() => router.push("/industry/collaborations")}
      />
    </div>
  );
}
