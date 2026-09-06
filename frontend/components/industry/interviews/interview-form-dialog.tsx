"use client";

import { useId, useMemo, useState } from "react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { ApiError } from "@/lib/api";
import { rescheduleInterview, scheduleInterview } from "@/lib/industry/interviews";
import { applicantRef, OPPORTUNITY_TYPE_LABELS, type Application } from "@/types/application";
import {
  DURATION_OPTIONS,
  INTERVIEW_LOCATION_LABELS,
  INTERVIEW_LOCATION_PLACEHOLDERS,
  INTERVIEW_MODE_LABELS,
  INTERVIEW_MODES,
  type Interview,
  type InterviewMode,
} from "@/types/interview";

const selectClass =
  "h-9 w-full rounded-lg border border-input bg-transparent px-2.5 text-sm outline-none focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30";
const textareaClass =
  "w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30";

/** `datetime-local` needs "YYYY-MM-DDTHH:mm" in LOCAL time. */
function toLocalInputValue(iso: string | null): string {
  if (!iso) return "";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "";
  const pad = (n: number) => String(n).padStart(2, "0");
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}T${pad(d.getHours())}:${pad(
    d.getMinutes(),
  )}`;
}

interface FieldErrors {
  application?: string;
  scheduledAt?: string;
}

/** Outer shell. Mounts a FRESH <FormBody> every time it opens (and when
 * the target interview changes) so form state initialises straight from
 * props with no state-syncing effect. */
export function InterviewFormDialog({
  open,
  onOpenChange,
  mode,
  eligibleApplications = [],
  interview,
  onSubmitted,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  mode: "schedule" | "reschedule";
  eligibleApplications?: Application[];
  interview?: Interview;
  onSubmitted: (interview: Interview) => void;
}) {
  if (!open) return null;

  return (
    <Dialog open onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle>
            {mode === "schedule" ? "Schedule interview" : "Reschedule interview"}
          </DialogTitle>
          <DialogDescription>
            {mode === "schedule"
              ? "Set a time for a shortlisted candidate. Times are shown in your local timezone."
              : "Change the time or details of this scheduled interview."}
          </DialogDescription>
        </DialogHeader>

        <FormBody
          key={mode === "reschedule" ? (interview?.id ?? "new") : "new"}
          mode={mode}
          eligibleApplications={eligibleApplications}
          interview={interview}
          onSubmitted={(iv) => {
            onSubmitted(iv);
            onOpenChange(false);
          }}
          onCancel={() => onOpenChange(false)}
        />
      </DialogContent>
    </Dialog>
  );
}

function FormBody({
  mode,
  eligibleApplications,
  interview,
  onSubmitted,
  onCancel,
}: {
  mode: "schedule" | "reschedule";
  eligibleApplications: Application[];
  interview?: Interview;
  onSubmitted: (interview: Interview) => void;
  onCancel: () => void;
}) {
  const ids = {
    application: useId(),
    scheduledAt: useId(),
    duration: useId(),
    mode: useId(),
    location: useId(),
    notes: useId(),
  };

  const [applicationId, setApplicationId] = useState(() =>
    mode === "reschedule" && interview
      ? interview.application_id
      : eligibleApplications.length === 1
        ? eligibleApplications[0].id
        : "",
  );
  const [scheduledAt, setScheduledAt] = useState(() =>
    mode === "reschedule" && interview ? toLocalInputValue(interview.scheduled_at) : "",
  );
  const [duration, setDuration] = useState(() =>
    mode === "reschedule" && interview ? interview.duration_minutes : 30,
  );
  const [interviewMode, setInterviewMode] = useState<InterviewMode>(() =>
    mode === "reschedule" && interview ? interview.mode : "ONLINE",
  );
  const [location, setLocation] = useState(() =>
    mode === "reschedule" && interview ? (interview.location ?? "") : "",
  );
  const [notes, setNotes] = useState(() =>
    mode === "reschedule" && interview ? (interview.notes ?? "") : "",
  );

  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});

  const minDateTime = useMemo(() => toLocalInputValue(new Date().toISOString()), []);

  function validate(): boolean {
    const errs: FieldErrors = {};
    if (mode === "schedule" && !applicationId) {
      errs.application = "Choose a candidate to interview.";
    }
    if (!scheduledAt) {
      errs.scheduledAt = "Pick a date and time.";
    } else {
      const when = new Date(scheduledAt);
      if (Number.isNaN(when.getTime())) errs.scheduledAt = "That date and time isn't valid.";
      else if (when.getTime() <= Date.now())
        errs.scheduledAt = "The interview must be in the future.";
    }
    setFieldErrors(errs);
    return Object.keys(errs).length === 0;
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (submitting || !validate()) return;
    setSubmitting(true);
    setError(null);

    const scheduledIso = new Date(scheduledAt).toISOString();
    const trimmedLocation = location.trim() || null;
    const trimmedNotes = notes.trim() || null;

    try {
      const result =
        mode === "schedule"
          ? await scheduleInterview({
              application_id: applicationId,
              scheduled_at: scheduledIso,
              duration_minutes: duration,
              mode: interviewMode,
              location: trimmedLocation,
              notes: trimmedNotes,
            })
          : await rescheduleInterview(interview!.id, {
              scheduled_at: scheduledIso,
              duration_minutes: duration,
              mode: interviewMode,
              location: trimmedLocation,
              notes: trimmedNotes,
            });
      onSubmitted(result);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const noEligible = mode === "schedule" && eligibleApplications.length === 0;

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-4">
      <FormError message={error} />

      {mode === "schedule" ? (
        <div className="space-y-1.5">
          <Label htmlFor={ids.application}>Candidate</Label>
          {noEligible ? (
            <p className="text-sm text-muted-foreground">
              No shortlisted candidates are waiting for an interview.
            </p>
          ) : (
            <select
              id={ids.application}
              value={applicationId}
              onChange={(e) => setApplicationId(e.target.value)}
              disabled={submitting}
              className={selectClass}
              aria-invalid={!!fieldErrors.application}
            >
              <option value="">Select a candidate…</option>
              {eligibleApplications.map((app) => (
                <option key={app.id} value={app.id}>
                  {applicantRef(app.student_id)} ·{" "}
                  {app.opportunity?.title ?? OPPORTUNITY_TYPE_LABELS[app.opportunity_type]}
                </option>
              ))}
            </select>
          )}
          <FieldError id={`${ids.application}-error`} message={fieldErrors.application} />
        </div>
      ) : null}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
        <div className="space-y-1.5">
          <Label htmlFor={ids.scheduledAt}>Date &amp; time</Label>
          <Input
            id={ids.scheduledAt}
            type="datetime-local"
            value={scheduledAt}
            min={minDateTime}
            onChange={(e) => setScheduledAt(e.target.value)}
            disabled={submitting}
            aria-invalid={!!fieldErrors.scheduledAt}
          />
          <FieldError id={`${ids.scheduledAt}-error`} message={fieldErrors.scheduledAt} />
        </div>

        <div className="space-y-1.5">
          <Label htmlFor={ids.duration}>Duration</Label>
          <select
            id={ids.duration}
            value={duration}
            onChange={(e) => setDuration(Number(e.target.value))}
            disabled={submitting}
            className={selectClass}
          >
            {DURATION_OPTIONS.map((d) => (
              <option key={d} value={d}>
                {d} minutes
              </option>
            ))}
          </select>
        </div>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={ids.mode}>Format</Label>
        <select
          id={ids.mode}
          value={interviewMode}
          onChange={(e) => setInterviewMode(e.target.value as InterviewMode)}
          disabled={submitting}
          className={selectClass}
        >
          {INTERVIEW_MODES.map((m) => (
            <option key={m} value={m}>
              {INTERVIEW_MODE_LABELS[m]}
            </option>
          ))}
        </select>
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={ids.location}>
          {INTERVIEW_LOCATION_LABELS[interviewMode]}{" "}
          <span className="font-normal text-muted-foreground">(optional)</span>
        </Label>
        <Input
          id={ids.location}
          value={location}
          maxLength={2000}
          onChange={(e) => setLocation(e.target.value)}
          placeholder={INTERVIEW_LOCATION_PLACEHOLDERS[interviewMode]}
          disabled={submitting}
        />
      </div>

      <div className="space-y-1.5">
        <Label htmlFor={ids.notes}>
          Notes <span className="font-normal text-muted-foreground">(private, optional)</span>
        </Label>
        <textarea
          id={ids.notes}
          value={notes}
          rows={3}
          maxLength={10000}
          onChange={(e) => setNotes(e.target.value)}
          placeholder="Panel, focus areas, prep…"
          disabled={submitting}
          className={textareaClass}
        />
      </div>

      {mode === "schedule" && applicationId ? (
        <p className="text-xs text-muted-foreground">
          Scheduling will move this candidate to the “Interview scheduled” stage.
        </p>
      ) : null}

      <div className="flex flex-col-reverse gap-2 sm:flex-row sm:justify-end">
        <Button type="button" variant="outline" onClick={onCancel} disabled={submitting}>
          Cancel
        </Button>
        <Button type="submit" disabled={submitting || noEligible}>
          {submitting
            ? "Saving…"
            : mode === "schedule"
              ? "Schedule interview"
              : "Save changes"}
        </Button>
      </div>
    </form>
  );
}
