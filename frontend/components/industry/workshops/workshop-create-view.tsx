"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { createWorkshop } from "@/lib/industry/workshops";
import { ApiError } from "@/lib/api";
import { WorkshopForm } from "@/components/industry/workshops/workshop-form";
import type { WorkshopCreate } from "@/types/industry-workshop";

export function WorkshopCreateView() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(data: WorkshopCreate) {
    setSubmitting(true);
    setError(null);
    try {
      const created = await createWorkshop(data);
      router.push(`/industry/workshops/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the workshop. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Link
          href="/industry/workshops"
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> All workshops
        </Link>
        <div>
          <h1 className="text-xl font-semibold">Create Workshop</h1>
          <p className="text-sm text-muted-foreground">
            Saved as a draft. You can review and publish it afterwards.
          </p>
        </div>
      </div>

      <WorkshopForm
        mode="create"
        submitting={submitting}
        error={error}
        onSubmit={handleSubmit}
        onCancel={() => router.push("/industry/workshops")}
      />
    </div>
  );
}
