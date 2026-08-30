"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { RotateCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/auth/form-error";
import { createClient } from "@/lib/supabase/client";
import { scoreAttemptViaBackend } from "@/lib/student/assessments";

/** Lets a student retry backend scoring for an attempt stuck "submitted,
 * awaiting scoring" (e.g. the backend was briefly unreachable when they
 * first submitted). Refreshes the page on success so the server component
 * re-fetches the now-COMPLETED attempt. */
export function RetryScoringButton({ attemptId }: { attemptId: string }) {
  const router = useRouter();
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleRetry() {
    setLoading(true);
    setError(null);
    try {
      const supabase = createClient();
      const { error: scoreError } = await scoreAttemptViaBackend(supabase, attemptId);
      if (scoreError) {
        setError(scoreError);
        return;
      }
      router.refresh();
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="space-y-2">
      <FormError message={error} />
      <Button variant="outline" size="sm" onClick={handleRetry} disabled={loading}>
        <RotateCw className={loading ? "animate-spin" : ""} /> {loading ? "Scoring..." : "Try Scoring Now"}
      </Button>
    </div>
  );
}
