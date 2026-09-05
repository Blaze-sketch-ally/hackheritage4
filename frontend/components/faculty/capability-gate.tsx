"use client";

import Link from "next/link";
import { AlertCircle, Loader2, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  hasAssessmentCapability,
  useFacultyCapabilitiesContext,
  type AssessmentCapability,
} from "@/lib/faculty/capabilities";

/**
 * Phase 1 (Faculty Dashboard Architecture): one shared, reusable
 * client-side gate for Question Studio / Evaluation Workspace pages and
 * actions that require a specific capability -- Create Question,
 * Question Bank, Blueprints today; Evaluation Workspace later phases.
 *
 * This is UX only. The backend (require_assessment_author/reviewer/
 * evaluator) and RLS remain the real, authoritative enforcement
 * regardless of what this component shows or hides -- see
 * lib/faculty/capabilities.tsx's own docstring. Its only job is to stop
 * a capability-less Faculty member from filling out an entire form (or
 * staring at a table that will only ever be empty for them) only to
 * discover a 403 at the end, and to render a clean, honest "you don't
 * have this" state for anyone who reaches a protected page by a direct
 * URL rather than navigation -- never a crash, never a confusing raw
 * error, never any of the gated content underneath.
 *
 * `capability` checks a single capability; `anyOf` checks whether the
 * caller holds at least one of several (Question Studio's own
 * author-or-reviewer access model) -- pass exactly one.
 */
export function CapabilityGate({
  capability,
  anyOf,
  deniedMessage,
  children,
}: {
  capability?: AssessmentCapability;
  anyOf?: readonly AssessmentCapability[];
  deniedMessage: string;
  children: React.ReactNode;
}) {
  const state = useFacultyCapabilitiesContext();

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Checking your access…
        </CardContent>
      </Card>
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <p className="font-medium">Could not verify your access.</p>
          <p className="text-sm text-muted-foreground">{state.error.message}</p>
        </CardContent>
      </Card>
    );
  }

  const allowed = capability
    ? hasAssessmentCapability(state.capabilities, capability)
    : (anyOf ?? []).some((c) => hasAssessmentCapability(state.capabilities, c));

  if (!allowed) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <ShieldAlert className="size-8 text-muted-foreground" />
          <div>
            <p className="font-medium">You don&apos;t have permission to access this workspace.</p>
            <p className="text-sm text-muted-foreground">{deniedMessage}</p>
          </div>
          <Button variant="outline" size="sm" render={<Link href="/faculty/dashboard" />} nativeButton={false}>
            Back to your dashboard
          </Button>
        </CardContent>
      </Card>
    );
  }

  return <>{children}</>;
}
