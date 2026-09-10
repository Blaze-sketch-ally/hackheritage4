"use client";

import { useEffect, useId, useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { FormError } from "@/components/auth/form-error";
import { ApiError } from "@/lib/api";
import {
  createIndustryPartnerRelationship,
  searchIndustryPartnerCompanies,
  updateIndustryPartnerRelationship,
} from "@/lib/institution/industry-partners";
import type {
  CompanyOption,
  IndustryPartnerRelationshipResponse,
  IndustryPartnerStatus,
  IndustryPartnerRelationshipType,
} from "@/types/institution-industry";
import {
  RELATIONSHIP_STATUSES,
  RELATIONSHIP_STATUS_LABELS,
  RELATIONSHIP_TYPES,
  RELATIONSHIP_TYPE_LABELS,
} from "@/types/institution-industry";

/**
 * One dialog, two modes: `existing` absent creates a new tracked
 * relationship (company picker shown, required, sourced ONLY from the
 * real `industry_profiles` catalog via searchIndustryPartnerCompanies --
 * never a free-text company name); `existing` present edits the
 * relationship_type/status/notes for an already-tracked company (the
 * company itself is fixed, shown read-only). "Removing" a partner is
 * setting relationship_status to INACTIVE -- there is no delete.
 */
export function IndustryPartnerForm({
  open,
  onOpenChange,
  existing,
  existingCompanyName,
  presetCompanyId,
  presetCompanyName,
  defaultRelationshipType,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  existing?: { industryId: string; relationship: IndustryPartnerRelationshipResponse | null };
  existingCompanyName?: string | null;
  /** Pins the company for a NEW relationship (e.g. opened from a
   * Collaboration's "Add to Industry Partners" action) -- skips the
   * picker, same as edit mode's read-only company display, but still
   * creates (not updates) a relationship. */
  presetCompanyId?: string;
  presetCompanyName?: string | null;
  /** Initial relationship type for a new relationship -- still editable. */
  defaultRelationshipType?: IndustryPartnerRelationshipType;
  onSaved: (relationship: IndustryPartnerRelationshipResponse) => void;
}) {
  const isEdit = !!existing;
  const fixedCompanyId = existing?.industryId ?? presetCompanyId;
  const fixedCompanyName = existingCompanyName ?? presetCompanyName;

  const [companyId, setCompanyId] = useState(fixedCompanyId ?? "");
  const [companySearch, setCompanySearch] = useState("");
  const [companyOptions, setCompanyOptions] = useState<CompanyOption[]>([]);
  const [companiesError, setCompaniesError] = useState<string | null>(null);

  const [relationshipType, setRelationshipType] = useState<IndustryPartnerRelationshipType>(
    (existing?.relationship?.relationship_type as IndustryPartnerRelationshipType) ?? defaultRelationshipType ?? "OTHER",
  );
  const [relationshipStatus, setRelationshipStatus] = useState<IndustryPartnerStatus>(
    (existing?.relationship?.relationship_status as IndustryPartnerStatus) ?? "PROSPECT",
  );
  const [notes, setNotes] = useState(existing?.relationship?.notes ?? "");

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const typeId = useId();
  const statusId = useId();
  const notesId = useId();

  useEffect(() => {
    if (!open || fixedCompanyId) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      searchIndustryPartnerCompanies(companySearch)
        .then(({ companies }) => {
          if (!cancelled) setCompanyOptions(companies);
        })
        .catch((err) => {
          if (!cancelled) setCompaniesError(err instanceof ApiError ? err.message : "Could not load companies.");
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [open, fixedCompanyId, companySearch]);

  if (!open) return null;

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!fixedCompanyId && !companyId) {
      setError("Choose a company to track.");
      return;
    }
    setSubmitting(true);
    try {
      const saved =
        isEdit && existing
          ? await updateIndustryPartnerRelationship(existing.industryId, {
              relationship_type: relationshipType,
              relationship_status: relationshipStatus,
              notes: notes.trim() || null,
            })
          : await createIndustryPartnerRelationship({
              industry_id: fixedCompanyId ?? companyId,
              relationship_type: relationshipType,
              relationship_status: relationshipStatus,
              notes: notes.trim() || null,
            });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this industry partner. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{isEdit ? "Edit Relationship" : "Add Industry Partner"}</DialogTitle>
            <DialogDescription>
              Track how your institution relates to a company -- this is private to your institution and never
              shared with the company or other institutions.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <FormError message={error} />

            <div className="space-y-1.5">
              <Label>Company</Label>
              {fixedCompanyId ? (
                <p className="rounded-md border bg-muted/40 px-3 py-2 text-sm">
                  {fixedCompanyName ?? "Unknown company"}
                </p>
              ) : (
                <>
                  <Input
                    value={companySearch}
                    onChange={(e) => setCompanySearch(e.target.value)}
                    placeholder="Search companies..."
                    disabled={submitting}
                    aria-label="Search companies"
                  />
                  {companiesError ? (
                    <p className="text-sm text-destructive">{companiesError}</p>
                  ) : (
                    <Select value={companyId} onValueChange={(v) => setCompanyId(v ?? "")} disabled={submitting}>
                      <SelectTrigger className="w-full" aria-label="Company">
                        <SelectValue placeholder="Choose a company..." />
                      </SelectTrigger>
                      <SelectContent>
                        {companyOptions.length === 0 ? (
                          <div className="px-2 py-3 text-center text-sm text-muted-foreground">
                            No companies found.
                          </div>
                        ) : (
                          companyOptions.map((c) => (
                            <SelectItem key={c.id} value={c.id}>
                              {c.company_name ?? "(unnamed company)"}
                              {c.industry_sector ? ` · ${c.industry_sector}` : ""}
                            </SelectItem>
                          ))
                        )}
                      </SelectContent>
                    </Select>
                  )}
                </>
              )}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={typeId}>Relationship Type</Label>
              <Select
                value={relationshipType}
                onValueChange={(v) => setRelationshipType((v as IndustryPartnerRelationshipType) ?? "OTHER")}
                disabled={submitting}
              >
                <SelectTrigger id={typeId} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RELATIONSHIP_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {RELATIONSHIP_TYPE_LABELS[t]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={statusId}>Status</Label>
              <Select
                value={relationshipStatus}
                onValueChange={(v) => setRelationshipStatus((v as IndustryPartnerStatus) ?? "PROSPECT")}
                disabled={submitting}
              >
                <SelectTrigger id={statusId} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {RELATIONSHIP_STATUSES.map((s) => (
                    <SelectItem key={s} value={s}>
                      {RELATIONSHIP_STATUS_LABELS[s]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              {isEdit ? (
                <p className="text-xs text-muted-foreground">
                  Set to Inactive to stop treating this as an active partner -- there is no delete.
                </p>
              ) : null}
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={notesId}>Notes (optional, private to your institution)</Label>
              <Textarea
                id={notesId}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                maxLength={3000}
                disabled={submitting}
              />
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving..." : isEdit ? "Save Changes" : "Add Partner"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
