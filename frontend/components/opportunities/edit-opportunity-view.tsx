"use client";

import { useEffect, useState } from "react";
import { AlertCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { OpportunityForm } from "@/components/opportunities/opportunity-form";
import { OpportunitySkillEditor } from "@/components/opportunities/opportunity-skill-editor";
import { ApiError } from "@/lib/api";
import { getOpportunity } from "@/lib/industry/opportunities";
import type { Opportunity } from "@/types/opportunity";

export function EditOpportunityView({ opportunityId }: { opportunityId: string }) {
  const [opportunity, setOpportunity] = useState<Opportunity | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const row = await getOpportunity(opportunityId);
        if (cancelled) return;
        setOpportunity(row);
        setError(null);
      } catch (err) {
        if (cancelled) return;
        setError(err instanceof ApiError ? err : new ApiError(0, "Could not load this opportunity."));
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [opportunityId, reloadKey]);

  if (error) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load this opportunity.</p>
            <p className="text-sm text-muted-foreground">{error.message}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  if (!opportunity) {
    return <div className="h-40 animate-pulse rounded-lg bg-muted" aria-busy="true" aria-label="Loading opportunity" />;
  }

  return (
    <div className="space-y-4">
      <Badge variant="outline">{opportunity.status}</Badge>
      <OpportunityForm mode="edit" opportunity={opportunity} onSaved={() => setReloadKey((k) => k + 1)} />
      {opportunity.status === "DRAFT" ? (
        <OpportunitySkillEditor opportunityId={opportunityId} />
      ) : (
        <Card>
          <CardContent className="py-4 text-sm text-muted-foreground">
            Required skills are locked once an opportunity leaves draft — this keeps every applicant&apos;s match
            score computed against the exact requirements they applied under.
          </CardContent>
        </Card>
      )}
    </div>
  );
}
