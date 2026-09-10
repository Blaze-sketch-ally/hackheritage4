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
import { searchIndustryPartnerCompanies } from "@/lib/institution/industry-partners";
import { createIndustryConnection, updateIndustryConnection } from "@/lib/institution/industry-connections";
import type { CompanyOption } from "@/types/institution-industry";
import type { ContactType, IndustryConnectionRow } from "@/types/institution-industry-connection";
import { CONTACT_TYPE_LABELS, CONTACT_TYPES } from "@/types/institution-industry-connection";

/**
 * One dialog, two modes: `connection` absent creates a new contact
 * (company picker shown, required, sourced ONLY from the real
 * industry_profiles catalog -- reuses Phase 8's own company search
 * endpoint, never a free-text company name); `connection` present edits
 * the contact fields (the company itself is fixed, shown read-only).
 * "Removing" a connection is is_active=false -- there is no delete.
 */
export function IndustryConnectionForm({
  open,
  onOpenChange,
  connection,
  presetCompanyId,
  presetCompanyName,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  connection?: IndustryConnectionRow;
  /** Pins the company for a NEW connection (e.g. opened from Company Detail) -- skips the picker. */
  presetCompanyId?: string;
  presetCompanyName?: string | null;
  onSaved: (connection: IndustryConnectionRow) => void;
}) {
  const isEdit = !!connection;
  const fixedCompanyId = connection?.industry_id ?? presetCompanyId;
  const fixedCompanyName = connection?.company_name ?? presetCompanyName;

  const [companyId, setCompanyId] = useState(fixedCompanyId ?? "");
  const [companySearch, setCompanySearch] = useState("");
  const [companyOptions, setCompanyOptions] = useState<CompanyOption[]>([]);
  const [companiesError, setCompaniesError] = useState<string | null>(null);

  const [contactName, setContactName] = useState(connection?.contact_name ?? "");
  const [designation, setDesignation] = useState(connection?.designation ?? "");
  const [contactType, setContactType] = useState<ContactType>((connection?.contact_type as ContactType) ?? "OTHER");
  const [email, setEmail] = useState(connection?.email ?? "");
  const [phone, setPhone] = useState(connection?.phone ?? "");
  const [notes, setNotes] = useState(connection?.notes ?? "");
  const [isActive, setIsActive] = useState(connection?.is_active ?? true);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const nameId = useId();
  const designationId = useId();
  const typeId = useId();
  const emailId = useId();
  const phoneId = useId();
  const notesId = useId();
  const statusId = useId();

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
      setError("Choose a company for this contact.");
      return;
    }
    if (!contactName.trim()) {
      setError("Contact name is required.");
      return;
    }
    setSubmitting(true);
    try {
      const saved =
        isEdit && connection
          ? await updateIndustryConnection(connection.id, {
              contact_name: contactName.trim(),
              designation: designation.trim() || null,
              contact_type: contactType,
              email: email.trim() || null,
              phone: phone.trim() || null,
              notes: notes.trim() || null,
              is_active: isActive,
            })
          : await createIndustryConnection({
              industry_id: fixedCompanyId ?? companyId,
              contact_name: contactName.trim(),
              designation: designation.trim() || null,
              contact_type: contactType,
              email: email.trim() || null,
              phone: phone.trim() || null,
              notes: notes.trim() || null,
            });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this contact. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-md">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{isEdit ? "Edit Contact" : "Add Industry Connection"}</DialogTitle>
            <DialogDescription>
              Your institution&apos;s own record of a contact person at a company -- private to your institution.
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
              <Label htmlFor={nameId}>Contact Name</Label>
              <Input
                id={nameId}
                value={contactName}
                onChange={(e) => setContactName(e.target.value)}
                placeholder="e.g. Priya Sharma"
                maxLength={200}
                disabled={submitting}
                autoFocus
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={designationId}>Designation (optional)</Label>
              <Input
                id={designationId}
                value={designation}
                onChange={(e) => setDesignation(e.target.value)}
                placeholder="e.g. HR Manager"
                maxLength={200}
                disabled={submitting}
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={typeId}>Connection Type</Label>
              <Select
                value={contactType}
                onValueChange={(v) => setContactType((v as ContactType) ?? "OTHER")}
                disabled={submitting}
              >
                <SelectTrigger id={typeId} className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {CONTACT_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {CONTACT_TYPE_LABELS[t]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor={emailId}>Email (optional)</Label>
                <Input
                  id={emailId}
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  maxLength={254}
                  disabled={submitting}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={phoneId}>Phone (optional)</Label>
                <Input
                  id={phoneId}
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  maxLength={20}
                  disabled={submitting}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={notesId}>Notes (optional, private to your institution)</Label>
              <Textarea
                id={notesId}
                value={notes}
                onChange={(e) => setNotes(e.target.value)}
                rows={3}
                maxLength={2000}
                disabled={submitting}
              />
            </div>

            {isEdit ? (
              <div className="space-y-1.5">
                <Label htmlFor={statusId}>Status</Label>
                <Select
                  value={isActive ? "active" : "inactive"}
                  onValueChange={(v) => setIsActive(v !== "inactive")}
                  disabled={submitting}
                >
                  <SelectTrigger id={statusId} className="w-full">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="active">Active</SelectItem>
                    <SelectItem value="inactive">Inactive</SelectItem>
                  </SelectContent>
                </Select>
                <p className="text-xs text-muted-foreground">
                  Deactivating keeps the contact on file without showing it as a current connection.
                </p>
              </div>
            ) : null}
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving..." : isEdit ? "Save Changes" : "Add Contact"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
