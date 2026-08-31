"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertCircle, ArrowLeft } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { createInternship } from "@/lib/industry/internships";
import { getSkillCatalog, type CatalogSkill } from "@/lib/industry/skills";
import { InternshipForm } from "@/components/industry/opportunity-form";
import type { InternshipCreate } from "@/types/internship";

export function InternshipCreateView() {
  const router = useRouter();
  const [catalog, setCatalog] = useState<CatalogSkill[] | null>(null);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getSkillCatalog()
      .then(({ skills }) => {
        if (!cancelled) setCatalog(skills);
      })
      .catch(() => {
        if (!cancelled) {
          setCatalog([]);
          setLoadError("The skill catalog couldn't be loaded — you can still save a draft and add skills later.");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  async function handleSubmit(data: InternshipCreate) {
    setSubmitting(true);
    setError(null);
    try {
      const created = await createInternship(data);
      router.push(`/industry/internships/${created.id}`);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Could not create the internship. Please try again.",
      );
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Link
          href="/industry/internships"
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> All internships
        </Link>
        <div>
          <h1 className="text-xl font-semibold">Create Internship</h1>
          <p className="text-sm text-muted-foreground">
            Saved as a draft. You can review and publish it afterwards.
          </p>
        </div>
      </div>

      {loadError ? (
        <div className="flex items-start gap-2 rounded-lg border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-sm text-amber-700 dark:text-amber-400">
          <AlertCircle className="mt-0.5 size-4 shrink-0" aria-hidden="true" />
          <span>{loadError}</span>
        </div>
      ) : null}

      {catalog === null ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading…
          </CardContent>
        </Card>
      ) : (
        <InternshipForm
          mode="create"
          catalog={catalog}
          submitting={submitting}
          error={error}
          onSubmit={handleSubmit}
          onCancel={() => router.push("/industry/internships")}
        />
      )}
    </div>
  );
}
