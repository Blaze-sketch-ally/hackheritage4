"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { createOpportunity, updateOpportunity } from "@/lib/industry/opportunities";
import type { Opportunity, OpportunityType } from "@/types/opportunity";

const TYPE_ITEMS: Record<OpportunityType, string> = { JOB: "Job", INTERNSHIP: "Internship" };

/** Handles both create and edit -- one form, not two near-identical
 * copies for jobs vs internships (opportunity_type is just a field in
 * this same form). `lockedType`, when set, pre-selects and disables the
 * type field -- used by /industry/jobs/create and
 * /industry/internships/create so creating from either section produces
 * the right type without extra clicks, still going through this same
 * component. */
export function OpportunityForm({
  mode,
  opportunity,
  lockedType,
  onSaved,
}: {
  mode: "create" | "edit";
  opportunity?: Opportunity;
  lockedType?: OpportunityType;
  /** Called after a successful edit-mode save. Required for edit mode
   * because the parent (EditOpportunityView) fetches opportunity data
   * itself in a Client Component -- router.refresh() only re-runs Server
   * Components, so it cannot update that local state on its own. */
  onSaved?: () => void;
}) {
  const router = useRouter();
  const [title, setTitle] = useState(opportunity?.title ?? "");
  const [description, setDescription] = useState(opportunity?.description ?? "");
  const [location, setLocation] = useState(opportunity?.location ?? "");
  const [opportunityType, setOpportunityType] = useState<OpportunityType>(
    opportunity?.opportunity_type ?? lockedType ?? "INTERNSHIP",
  );
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const isClosed = opportunity?.status === "CLOSED";
  const typeLocked = mode === "create" ? Boolean(lockedType) : opportunity?.status !== "DRAFT";

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      if (mode === "create") {
        const created = await createOpportunity({
          title,
          description: description || null,
          location: location || null,
          opportunity_type: opportunityType,
        });
        router.push(`/industry/opportunities/${created.id}/edit`);
        return;
      }
      if (!opportunity) return;
      await updateOpportunity(opportunity.id, {
        title,
        description: description || null,
        location: location || null,
        ...(typeLocked ? {} : { opportunity_type: opportunityType }),
      });
      router.refresh();
      onSaved?.();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this opportunity.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">{mode === "create" ? "New Opportunity" : "Details"}</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="space-y-1.5">
            <Label htmlFor="opp-title">Title</Label>
            <Input id="opp-title" value={title} onChange={(e) => setTitle(e.target.value)} required disabled={isClosed} />
          </div>

          <div className="grid gap-4 sm:grid-cols-2">
            <div className="space-y-1.5">
              <Label htmlFor="opp-type">Type</Label>
              <Select
                value={opportunityType}
                onValueChange={(v) => v && setOpportunityType(v as OpportunityType)}
                items={TYPE_ITEMS}
                disabled={typeLocked || isClosed}
              >
                <SelectTrigger id="opp-type" className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="JOB">Job</SelectItem>
                  <SelectItem value="INTERNSHIP">Internship</SelectItem>
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <Label htmlFor="opp-location">Location</Label>
              <Input
                id="opp-location"
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                placeholder="Remote, Bengaluru, ..."
                disabled={isClosed}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <Label htmlFor="opp-description">Description</Label>
            <Textarea
              id="opp-description"
              value={description}
              onChange={(e) => setDescription(e.target.value)}
              rows={4}
              disabled={isClosed}
            />
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

          {!isClosed && (
            <Button type="submit" disabled={saving}>
              {saving ? "Saving..." : mode === "create" ? "Create Draft" : "Save Changes"}
            </Button>
          )}
          {isClosed && <p className="text-sm text-muted-foreground">This opportunity is closed and can no longer be edited.</p>}
        </form>
      </CardContent>
    </Card>
  );
}
