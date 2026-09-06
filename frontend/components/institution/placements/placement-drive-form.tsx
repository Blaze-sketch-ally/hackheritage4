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
import { SearchBar } from "@/components/common/search-bar";
import { FormError } from "@/components/auth/form-error";
import { ApiError } from "@/lib/api";
import { getInstitutionDepartments } from "@/lib/institution/departments";
import { getSkillCatalog, type CatalogSkill } from "@/lib/industry/skills";
import { createPlacementDrive, getAvailablePlacementJobs, updatePlacementDrive } from "@/lib/institution/placements";
import type { AvailableJobOption, DriveMode, PlacementDriveDetail } from "@/types/institution-placement";
import type { DepartmentSummary } from "@/types/institution-department";

const NONE = "__none__";

/**
 * One dialog, two modes: `drive` absent creates a new drive (job picker
 * shown, required); `drive` present edits it (job is fixed at creation --
 * see PlacementDriveUpdate's own docstring in the backend schema -- so
 * the job is shown read-only instead of as a picker).
 */
export function PlacementDriveForm({
  open,
  onOpenChange,
  drive,
  onSaved,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  drive?: PlacementDriveDetail;
  onSaved: (drive: PlacementDriveDetail) => void;
}) {
  const [jobId, setJobId] = useState(drive?.job_id ?? "");
  const [jobOptions, setJobOptions] = useState<AvailableJobOption[]>([]);
  const [jobsError, setJobsError] = useState<string | null>(null);

  const [title, setTitle] = useState(drive?.title ?? "");
  const [description, setDescription] = useState(drive?.description ?? "");
  const [applicationDeadline, setApplicationDeadline] = useState(drive?.application_deadline ?? "");
  const [driveDate, setDriveDate] = useState(drive?.drive_date ?? "");
  const [mode, setMode] = useState<DriveMode | typeof NONE>(drive?.mode ?? NONE);
  const [venue, setVenue] = useState(drive?.venue ?? "");
  const [instructions, setInstructions] = useState(drive?.instructions ?? "");

  const [departments, setDepartments] = useState<DepartmentSummary[]>([]);
  const [selectedDepartments, setSelectedDepartments] = useState<string[]>(drive?.eligible_department_ids ?? []);

  const [batchInput, setBatchInput] = useState("");
  const [batches, setBatches] = useState<number[]>(drive?.eligible_batches ?? []);

  const [minimumCgpa, setMinimumCgpa] = useState(
    drive?.minimum_cgpa != null ? String(drive.minimum_cgpa) : "",
  );

  const [skillSearch, setSkillSearch] = useState("");
  const [skillMatches, setSkillMatches] = useState<CatalogSkill[]>([]);
  const [selectedSkills, setSelectedSkills] = useState<{ id: string; name: string }[]>(
    (drive?.eligible_skill_ids ?? []).map((id, i) => ({ id, name: drive?.eligible_skill_names?.[i] ?? id })),
  );

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const titleId = useId();
  const descriptionId = useId();
  const deadlineId = useId();
  const driveDateId = useId();
  const venueId = useId();
  const instructionsId = useId();
  const cgpaId = useId();

  useEffect(() => {
    if (!open || drive) return;
    getAvailablePlacementJobs()
      .then(({ jobs }) => setJobOptions(jobs))
      .catch((err) => setJobsError(err instanceof ApiError ? err.message : "Could not load open jobs."));
  }, [open, drive]);

  useEffect(() => {
    if (!open) return;
    getInstitutionDepartments()
      .then(({ departments: rows }) => setDepartments(rows.filter((d) => d.is_active)))
      .catch(() => setDepartments([]));
  }, [open]);

  useEffect(() => {
    const query = skillSearch.trim();
    if (!open || !query) return;
    let cancelled = false;
    const timer = setTimeout(() => {
      getSkillCatalog(query)
        .then(({ skills }) => {
          if (!cancelled) setSkillMatches(skills);
        })
        .catch(() => {
          if (!cancelled) setSkillMatches([]);
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [open, skillSearch]);

  const visibleSkillMatches = skillSearch.trim() ? skillMatches : [];

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

  function addSkill(skill: CatalogSkill) {
    if (!selectedSkills.some((s) => s.id === skill.id)) {
      setSelectedSkills((prev) => [...prev, { id: skill.id, name: skill.name }]);
    }
    setSkillSearch("");
  }

  function removeSkill(id: string) {
    setSelectedSkills((prev) => prev.filter((s) => s.id !== id));
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    if (!drive && !jobId) {
      setError("Choose a job for this drive to coordinate.");
      return;
    }
    if (!title.trim()) {
      setError("Drive title is required.");
      return;
    }
    setSubmitting(true);
    try {
      const shared = {
        title: title.trim(),
        description: description.trim() || null,
        application_deadline: applicationDeadline || null,
        drive_date: driveDate || null,
        mode: mode === NONE ? null : mode,
        venue: venue.trim() || null,
        instructions: instructions.trim() || null,
        eligible_department_ids: selectedDepartments,
        eligible_batches: batches,
        minimum_cgpa: minimumCgpa.trim() ? Number(minimumCgpa) : null,
        eligible_skill_ids: selectedSkills.map((s) => s.id),
      };
      const saved = drive
        ? await updatePlacementDrive(drive.id, shared)
        : await createPlacementDrive({ job_id: jobId, ...shared });
      onSaved(saved);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not save the placement drive. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-lg">
        <form onSubmit={handleSubmit}>
          <DialogHeader>
            <DialogTitle>{drive ? "Edit Placement Drive" : "New Placement Drive"}</DialogTitle>
            <DialogDescription>
              A placement drive coordinates your students&apos; participation in an existing company job posting.
            </DialogDescription>
          </DialogHeader>

          <div className="space-y-4 py-2">
            <FormError message={error} />

            {drive ? (
              <div className="space-y-1.5">
                <Label>Job</Label>
                <p className="rounded-md border bg-muted/40 px-3 py-2 text-sm">
                  {drive.job_title ?? "Untitled job"}
                  {drive.company_name ? ` · ${drive.company_name}` : ""}
                </p>
                <p className="text-xs text-muted-foreground">The job a drive coordinates cannot be changed.</p>
              </div>
            ) : (
              <div className="space-y-1.5">
                <Label>Job</Label>
                {jobsError ? (
                  <p className="text-sm text-destructive">{jobsError}</p>
                ) : (
                  <Select value={jobId} onValueChange={(v) => setJobId(v ?? "")} disabled={submitting}>
                    <SelectTrigger className="w-full" aria-label="Job">
                      <SelectValue placeholder="Choose a published job..." />
                    </SelectTrigger>
                    <SelectContent>
                      {jobOptions.length === 0 ? (
                        <div className="px-2 py-3 text-center text-sm text-muted-foreground">
                          No published jobs available right now.
                        </div>
                      ) : (
                        jobOptions.map((job) => (
                          <SelectItem key={job.id} value={job.id}>
                            {job.title}
                            {job.company_name ? ` · ${job.company_name}` : ""}
                          </SelectItem>
                        ))
                      )}
                    </SelectContent>
                  </Select>
                )}
              </div>
            )}

            <div className="space-y-1.5">
              <Label htmlFor={titleId}>Drive Title</Label>
              <Input
                id={titleId}
                value={title}
                onChange={(e) => setTitle(e.target.value)}
                placeholder="e.g. Campus Drive – Software Engineer 2026"
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

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label htmlFor={deadlineId}>Application Deadline</Label>
                <Input
                  id={deadlineId}
                  type="date"
                  value={applicationDeadline ?? ""}
                  onChange={(e) => setApplicationDeadline(e.target.value)}
                  disabled={submitting}
                />
              </div>
              <div className="space-y-1.5">
                <Label htmlFor={driveDateId}>Drive Date</Label>
                <Input
                  id={driveDateId}
                  type="date"
                  value={driveDate ?? ""}
                  onChange={(e) => setDriveDate(e.target.value)}
                  disabled={submitting}
                />
              </div>
            </div>

            <div className="grid gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <Label>Mode</Label>
                <Select value={mode} onValueChange={(v) => setMode(v as DriveMode | typeof NONE)} disabled={submitting}>
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
                <Input
                  id={venueId}
                  value={venue ?? ""}
                  onChange={(e) => setVenue(e.target.value)}
                  maxLength={300}
                  disabled={submitting}
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <Label htmlFor={instructionsId}>Instructions for students (optional)</Label>
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
                <p className="text-sm font-medium">Eligibility Criteria</p>
                <p className="text-xs text-muted-foreground">
                  Leave a criterion empty to place no restriction on it. Only students linked to your institution
                  are ever considered.
                </p>
              </div>

              <div className="space-y-1.5">
                <Label>Eligible Departments</Label>
                {departments.length === 0 ? (
                  <p className="text-xs text-muted-foreground/70">No departments set up yet.</p>
                ) : (
                  <div className="flex flex-wrap gap-1.5">
                    {departments.map((dept) => (
                      <button
                        key={dept.id}
                        type="button"
                        disabled={submitting}
                        onClick={() => toggleDepartment(dept.id)}
                      >
                        <Badge variant={selectedDepartments.includes(dept.id) ? "default" : "outline"}>
                          {dept.name}
                        </Badge>
                      </button>
                    ))}
                  </div>
                )}
              </div>

              <div className="space-y-1.5">
                <Label>Eligible Batches</Label>
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
                        <button
                          type="button"
                          onClick={() => removeBatch(year)}
                          disabled={submitting}
                          aria-label={`Remove batch ${year}`}
                        >
                          <X className="size-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>

              <div className="space-y-1.5">
                <Label htmlFor={cgpaId}>Minimum CGPA</Label>
                <Input
                  id={cgpaId}
                  type="number"
                  min={0}
                  max={10}
                  step={0.1}
                  value={minimumCgpa}
                  onChange={(e) => setMinimumCgpa(e.target.value)}
                  placeholder="e.g. 7.5"
                  className="w-32"
                  disabled={submitting}
                />
              </div>

              <div className="space-y-1.5">
                <Label>Required Skills</Label>
                <SearchBar value={skillSearch} onChange={setSkillSearch} placeholder="Search the skill catalog..." />
                {skillSearch.trim() ? (
                  <div className="max-h-40 space-y-1 overflow-y-auto rounded-lg border p-1">
                    {visibleSkillMatches.filter((s) => !selectedSkills.some((sel) => sel.id === s.id)).length === 0 ? (
                      <p className="px-2 py-2 text-center text-xs text-muted-foreground">No matching skills.</p>
                    ) : (
                      visibleSkillMatches
                        .filter((s) => !selectedSkills.some((sel) => sel.id === s.id))
                        .map((skill) => (
                          <button
                            key={skill.id}
                            type="button"
                            disabled={submitting}
                            onClick={() => addSkill(skill)}
                            className="block w-full rounded-md px-2 py-1.5 text-left text-sm hover:bg-muted"
                          >
                            {skill.name}
                          </button>
                        ))
                    )}
                  </div>
                ) : null}
                {selectedSkills.length > 0 ? (
                  <div className="flex flex-wrap gap-1.5">
                    {selectedSkills.map((skill) => (
                      <Badge key={skill.id} variant="secondary" className="gap-1">
                        {skill.name}
                        <button
                          type="button"
                          onClick={() => removeSkill(skill.id)}
                          disabled={submitting}
                          aria-label={`Remove ${skill.name}`}
                        >
                          <X className="size-3" />
                        </button>
                      </Badge>
                    ))}
                  </div>
                ) : null}
              </div>
            </div>
          </div>

          <DialogFooter>
            <Button type="button" variant="outline" onClick={() => onOpenChange(false)} disabled={submitting}>
              Cancel
            </Button>
            <Button type="submit" disabled={submitting}>
              {submitting ? "Saving..." : drive ? "Save Changes" : "Create Drive"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
