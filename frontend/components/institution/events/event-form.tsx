"use client";

import { useEffect, useId, useState } from "react";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
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
import { getInstitutionDepartments } from "@/lib/institution/departments";
import { searchIndustryPartnerCompanies } from "@/lib/institution/industry-partners";
import { createInstitutionEvent, updateInstitutionEvent } from "@/lib/institution/events";
import type { DepartmentSummary } from "@/types/institution-department";
import type { CompanyOption } from "@/types/institution-industry";
import type { EventDetail, EventMode, EventType } from "@/types/institution-event";
import { EVENT_TYPE_LABELS, EVENT_TYPES } from "@/types/institution-event";

const NONE = "__none__";

function toDatetimeLocal(value: string | null): string {
  if (!value) return "";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${parsed.getFullYear()}-${pad(parsed.getMonth() + 1)}-${pad(parsed.getDate())}T${pad(parsed.getHours())}:${pad(parsed.getMinutes())}`;
}

/**
 * One dialog, two modes: `event` absent creates a new institution-
 * organized event (always DRAFT); `event` present edits it. Only ever
 * operates on `institution_events` rows -- a platform-wide Industry
 * workshop (event.source === "INDUSTRY_WORKSHOP") is never editable
 * here, and the caller (EventDetailView) never renders this form for one.
 * The company picker is sourced ONLY from the real industry_profiles
 * catalog (reusing Phase 8's search endpoint) -- never a free-text name.
 */
export function EventForm({
  open,
  onOpenChange,
  event,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  event?: EventDetail;
  onSaved: (event: EventDetail) => void;
}) {
  const isEdit = !!event;

  const [title, setTitle] = useState(event?.title ?? "");
  const [description, setDescription] = useState(event?.description ?? "");
  const [eventType, setEventType] = useState<EventType>((event?.event_type as EventType) ?? "OTHER");
  const [mode, setMode] = useState<EventMode | typeof NONE>((event?.mode as EventMode) ?? NONE);
  const [venue, setVenue] = useState(event?.venue ?? "");
  const [startAt, setStartAt] = useState(toDatetimeLocal(event?.start_at ?? null));
  const [endAt, setEndAt] = useState(toDatetimeLocal(event?.end_at ?? null));
  const [registrationDeadline, setRegistrationDeadline] = useState(
    toDatetimeLocal(event?.registration_deadline ?? null),
  );
  const [instructions, setInstructions] = useState(event?.instructions ?? "");
  const [includesFaculty, setIncludesFaculty] = useState(event?.includes_faculty ?? false);

  const [companyId, setCompanyId] = useState(event?.industry_id ?? "");
  const [companySearch, setCompanySearch] = useState("");
  const [companyOptions, setCompanyOptions] = useState<CompanyOption[]>([]);
  const [companiesError, setCompaniesError] = useState<string | null>(null);

  const [departments, setDepartments] = useState<DepartmentSummary[]>([]);
  const [selectedDepartments, setSelectedDepartments] = useState<string[]>(event?.target_department_ids ?? []);

  const [batchInput, setBatchInput] = useState("");
  const [batches, setBatches] = useState<number[]>(event?.target_batches ?? []);

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const titleId = useId();
  const descriptionId = useId();
  const startId = useId();
  const endId = useId();
  const deadlineId = useId();
  const venueId = useId();
  const instructionsId = useId();

  useEffect(() => {
    if (!open) return;
    getInstitutionDepartments()
      .then(({ departments: rows }) => setDepartments(rows.filter((d) => d.is_active)))
      .catch(() => setDepartments([]));
  }, [open]);

  useEffect(() => {
    if (!open) return;
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
  }, [open, companySearch]);

  if (!open) return null;

  function toggleDepartment(id: string) {
    setSelectedDepartments((prev) => (prev.includes(id) ? prev.filter((d) => d !== id) : [...prev, id]));
  }

  function addBatch() {
    const year = Number(batchInput.trim());
    if (!Number.isInteger(year) || year < 1900 || year > 2200) return;
    if (!batches.includes(year)) setBatches((prev) => [...prev, year].sort((a, b) => a - b));
    setBatchInput("");
  }

  function removeBatch(year: number) {
    setBatches((prev) => prev.filter((b) => b !== year));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!title.trim()) {
      setError("Event title is required.");
      return;
    }
    setSubmitting(true);
    try {
      const shared = {
        title: title.trim(),
        description: description.trim() || null,
        event_type: eventType,
        industry_id: companyId || null,
        mode: mode === NONE ? null : mode,
        venue: venue.trim() || null,
        start_at: startAt ? new Date(startAt).toISOString() : null,
        end_at: endAt ? new Date(endAt).toISOString() : null,
        registration_deadline: registrationDeadline ? new Date(registrationDeadline).toISOString() : null,
        target_department_ids: selectedDepartments,
        target_batches: batches,
        includes_faculty: includesFaculty,
        instructions: instructions.trim() || null,
      };
      const saved = isEdit && event ? await updateInstitutionEvent(event.id, shared) : await createInstitutionEvent(shared);
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save this event. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{isEdit ? "Edit Event" : "Create Event"}</DialogTitle>
            <DialogDescription>
              Organize a seminar, workshop, guest lecture or other session for your institution&apos;s students.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <FormError message={error} />

            <div className="space-y-1.5">
              <Label htmlFor={titleId}>Title</Label>
              <Input
                id={titleId}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Placement Orientation 2026"
                maxLength={200}
                disabled={submitting}
                autoFocus
              />
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={descriptionId}>Description (optional)</Label>
              <Textarea
                id={descriptionId}
                value={description ?? ""}
                onChange={(e) => setDescription(e.target.value)}
                rows={3}
                maxLength={5000}
                disabled={submitting}
              />
            </div>

            <div className="space-y-1.5">
              <Label>Event Type</Label>
              <Select value={eventType} onValueChange={(v) => setEventType((v as EventType) ?? "OTHER")} disabled={submitting}>
                <SelectTrigger className="w-full">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {EVENT_TYPES.map((t) => (
                    <SelectItem key={t} value={t}>
                      {EVENT_TYPE_LABELS[t]}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-1.5">
              <Label>Company (optional)</Label>
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
                    <SelectValue placeholder="No company featured" />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="">No company featured</SelectItem>
                    {companyOptions.map((c) => (
                      <SelectItem key={c.id} value={c.id}>
                        {c.company_name ?? "(unnamed company)"}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor={startId}>Start</Label>
                <Input
                  id={startId}
                  type="datetime-local"
                  value={startAt}
                  onChange={(e) => setStartAt(e.target.value)}
                  disabled={submitting}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={endId}>End (optional)</Label>
                <Input
                  id={endId}
                  type="datetime-local"
                  value={endAt}
                  onChange={(e) => setEndAt(e.target.value)}
                  disabled={submitting}
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Mode</Label>
                <Select value={mode} onValueChange={(v) => setMode((v as EventMode) ?? NONE)} disabled={submitting}>
                  <SelectTrigger className="w-full" aria-label="Mode">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value={NONE}>Unspecified</SelectItem>
                    <SelectItem value="ONSITE">Onsite</SelectItem>
                    <SelectItem value="REMOTE">Remote</SelectItem>
                    <SelectItem value="HYBRID">Hybrid</SelectItem>
                  </SelectContent>
                </Select>
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={venueId}>Venue (optional)</Label>
                <Input id={venueId} value={venue ?? ""} onChange={(e) => setVenue(e.target.value)} maxLength={300} disabled={submitting} />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={deadlineId}>Registration Deadline (optional, informational only)</Label>
              <Input
                id={deadlineId}
                type="datetime-local"
                value={registrationDeadline}
                onChange={(e) => setRegistrationDeadline(e.target.value)}
                disabled={submitting}
              />
              <p className="text-xs text-muted-foreground">
                There is no registration system in this app -- this is shown as information only.
              </p>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={instructionsId}>Instructions (optional)</Label>
              <Textarea
                id={instructionsId}
                value={instructions ?? ""}
                onChange={(e) => setInstructions(e.target.value)}
                rows={2}
                maxLength={3000}
                disabled={submitting}
              />
            </div>

            <div className="space-y-3 border-t pt-4">
              <div>
                <p className="text-sm font-medium">Audience</p>
                <p className="text-xs text-muted-foreground">
                  Leave departments/batches empty to target all students.
                </p>
              </div>

              <div className="space-y-1.5">
                <Label>Target Departments</Label>
                {departments.length === 0 ? (
                  <p className="text-xs text-muted-foreground/70">No departments set up yet.</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {departments.map((dept) => (
                      <button key={dept.id} type="button" disabled={submitting} onClick={() => toggleDepartment(dept.id)}>
                        <Badge variant={selectedDepartments.includes(dept.id) ? "default" : "outline"}>{dept.name}</Badge>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <Label>Target Batches</Label>
                <div className="flex gap-2">
                  <Input
                    value={batchInput}
                    onChange={(e) => setBatchInput(e.target.value)}
                    onKeyDown={(e) => {
                      if (e.key === "Enter") {
                        e.preventDefault();
                        addBatch();
                      }
                    }}
                    placeholder="e.g. 2026"
                    inputMode="numeric"
                    className="w-32"
                    disabled={submitting}
                  />
                  <Button type="button" variant="outline" size="sm" onClick={addBatch} disabled={submitting}>
                    Add
                  </Button>
                </div>
                {batches.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {batches.map((year) => (
                      <Badge key={year} variant="secondary" className="gap-1">
                        {year}
                        <button type="button" onClick={() => removeBatch(year)} disabled={submitting} aria-label={`Remove batch ${year}`}>
                          <X className="size-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="flex items-center gap-2">
                <input
                  id="includes-faculty"
                  type="checkbox"
                  checked={includesFaculty}
                  onChange={(e) => setIncludesFaculty(e.target.checked)}
                  disabled={submitting}
                  className="size-4"
                />
                <Label htmlFor="includes-faculty" className="font-normal">
                  Also targets faculty
                </Label>
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving..." : isEdit ? "Save Changes" : "Create Event"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
