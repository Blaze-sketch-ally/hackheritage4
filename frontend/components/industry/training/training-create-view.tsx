"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { createTraining } from "@/lib/industry/training";
import { ApiError } from "@/lib/api";
import { TrainingForm } from "@/components/industry/training/training-form";
import type { TrainingCreate } from "@/types/industry-training";

export function TrainingCreateView() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(data: TrainingCreate) {
    setSubmitting(true);
    setError(null);
    try {
      const created = await createTraining(data);
      router.push(`/industry/training/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the training record. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Link
          href="/industry/training"
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> All training
        </Link>
        <div>
          <h1 className="text-xl font-semibold">Create Training</h1>
          <p className="text-sm text-muted-foreground">
            Saved as a draft. You can review and publish it afterwards.
          </p>
        </div>
      </div>

      <TrainingForm
        mode="create"
        submitting={submitting}
        error={error}
        onSubmit={handleSubmit}
        onCancel={() => router.push("/industry/training")}
      />
    </div>
  );
}
