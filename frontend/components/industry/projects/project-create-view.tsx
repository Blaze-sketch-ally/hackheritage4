"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { ArrowLeft } from "lucide-react";
import { createProject } from "@/lib/industry/projects";
import { ApiError } from "@/lib/api";
import { ProjectForm } from "@/components/industry/projects/project-form";
import type { ProjectCreate } from "@/types/industry-project";

export function ProjectCreateView() {
  const router = useRouter();
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function handleSubmit(data: ProjectCreate) {
    setSubmitting(true);
    setError(null);
    try {
      const created = await createProject(data);
      router.push(`/industry/projects/${created.id}`);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not create the project. Please try again.");
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-6">
      <div className="space-y-2">
        <Link
          href="/industry/projects"
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> All projects
        </Link>
        <div>
          <h1 className="text-xl font-semibold">Create Project</h1>
          <p className="text-sm text-muted-foreground">
            Saved as a draft. You can review and publish it afterwards.
          </p>
        </div>
      </div>

      <ProjectForm
        mode="create"
        submitting={submitting}
        error={error}
        onSubmit={handleSubmit}
        onCancel={() => router.push("/industry/projects")}
      />
    </div>
  );
}
