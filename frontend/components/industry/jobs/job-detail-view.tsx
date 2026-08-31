"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { AlertCircle, ArrowLeft, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import {
  archiveJob,
  closeJob,
  getJob,
  publishJob,
  updateJob,
} from "@/lib/industry/jobs";
import { getSkillCatalog, type CatalogSkill } from "@/lib/industry/skills";
import { JobForm } from "@/components/industry/jobs/job-form";
import { JobActions } from "@/components/industry/jobs/job-actions";
import { JobStatusBadge } from "@/components/industry/jobs/job-status-badge";
import {
  EMPLOYMENT_TYPE_LABELS,
  SKILL_IMPORTANCE_LABELS,
  WORK_MODE_LABELS,
  type EmploymentType,
  type Job,
  type JobCreate,
  type WorkMode,
} from "@/types/job";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; job: Job };

type LifecycleAction = "publish" | "close" | "archive";

const ACTION_COPY: Record<
  LifecycleAction,
  { title: string; description: string; confirm: string; destructive: boolean; done: string }
> = {
  publish: {
    title: "Publish this job?",
    description: "Students will be able to see and apply to it.",
    confirm: "Publish",
    destructive: false,
    done: "Job published.",
  },
  close: {
    title: "Close this job?",
    description: "It stops accepting new applications. You can publish it again later.",
    confirm: "Close",
    destructive: false,
    done: "Job closed.",
  },
  archive: {
    title: "Archive this job?",
    description: "It's hidden from students and moved out of your active list. This can't be undone.",
    confirm: "Archive",
    destructive: true,
    done: "Job archived.",
  },
};

const RUNNERS: Record<LifecycleAction, (id: string) => Promise<Job>> = {
  publish: publishJob,
  close: closeJob,
  archive: archiveJob,
};

function formatDate(value: string | null): string {
  if (!value) return "Not set";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
  });
}

function formatSalary(job: Job): string | null {
  if (job.salary_min == null && job.salary_max == null) return null;
  const cur = job.salary_currency ?? "INR";
  if (job.salary_min != null && job.salary_max != null) {
    return `${cur} ${job.salary_min.toLocaleString()} – ${job.salary_max.toLocaleString()}`;
  }
  const one = (job.salary_min ?? job.salary_max) as number;
  return `${cur} ${one.toLocaleString()}${job.salary_min != null ? " (min)" : " (max)"}`;
}

function Detail({ label, children }: { label: string; children: React.ReactNode }) {
  const empty = children == null || children === "";
  return (
    <div className="space-y-0.5">
      <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className={empty ? "text-sm text-muted-foreground/60" : "text-sm"}>
        {empty ? "Not set" : children}
      </dd>
    </div>
  );
}

export function JobDetailView({
  jobId,
  initialEdit = false,
}: {
  jobId: string;
  initialEdit?: boolean;
}) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [catalog, setCatalog] = useState<CatalogSkill[]>([]);
  const [editing, setEditing] = useState(initialEdit);

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [pendingAction, setPendingAction] = useState<LifecycleAction | null>(null);
  const [confirming, setConfirming] = useState<LifecycleAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getJob(jobId)
      .then((job) => {
        if (!cancelled) setState({ status: "ready", job });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this job."),
        });
      });
    getSkillCatalog()
      .then(({ skills }) => {
        if (!cancelled) setCatalog(skills);
      })
      .catch(() => {
        /* the picker just shows an empty catalog */
      });
    return () => {
      cancelled = true;
    };
  }, [jobId, reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function handleSave(data: JobCreate) {
    setSaving(true);
    setFormError(null);
    try {
      const updated = await updateJob(jobId, data);
      setState({ status: "ready", job: updated });
      setEditing(false);
      setActionSuccess("Changes saved.");
    } catch (err) {
      setFormError(
        err instanceof ApiError ? err.message : "Could not save your changes. Please try again.",
      );
    } finally {
      setSaving(false);
    }
  }

  async function runAction(action: LifecycleAction) {
    setConfirming(null);
    setPendingAction(action);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await RUNNERS[action](jobId);
      setState({ status: "ready", job: updated });
      setActionSuccess(ACTION_COPY[action].done);
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setPendingAction(null);
    }
  }

  return (
    <div className="space-y-6">
      <Link
        href="/industry/jobs"
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> All jobs
      </Link>

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {state.error.status === 404
                  ? "This job doesn't exist or isn't yours."
                  : state.error.status === 401
                    ? "Your session has expired. Please sign in again."
                    : "Could not load this job."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status === 404 ? (
              <Button variant="outline" size="sm" render={<Link href="/industry/jobs" />}>
                Back to jobs
              </Button>
            ) : state.error.status !== 401 ? (
              <Button variant="outline" size="sm" onClick={reload}>
                <RefreshCw className="size-3.5" /> Try again
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? (
        <>
          <FormError message={actionError} />
          <FormSuccess message={actionSuccess} />

          {editing ? (
            <>
              <h1 className="text-xl font-semibold">Edit Job</h1>
              <JobForm
                mode="edit"
                catalog={catalog}
                initial={state.job}
                submitting={saving}
                error={formError}
                onSubmit={handleSave}
                onCancel={() => {
                  setEditing(false);
                  setFormError(null);
                }}
              />
            </>
          ) : (
            <ReadView
              job={state.job}
              pending={pendingAction !== null}
              canEdit={state.job.status === "DRAFT" || state.job.status === "PUBLISHED"}
              onEdit={() => setEditing(true)}
              onPublish={() => setConfirming("publish")}
              onClose={() => setConfirming("close")}
              onArchive={() => setConfirming("archive")}
            />
          )}
        </>
      ) : null}

      <ConfirmationDialog
        open={confirming !== null}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={confirming ? ACTION_COPY[confirming].title : ""}
        description={confirming ? ACTION_COPY[confirming].description : undefined}
        confirmLabel={confirming ? ACTION_COPY[confirming].confirm : "Confirm"}
        destructive={confirming ? ACTION_COPY[confirming].destructive : false}
        loading={pendingAction !== null}
        onConfirm={() => confirming && runAction(confirming)}
      />

      {state.status === "ready" && !editing ? (
        <p className="text-right">
          <Button variant="ghost" size="sm" onClick={() => router.push("/industry/jobs")}>
            Done
          </Button>
        </p>
      ) : null}
    </div>
  );
}

function ReadView({
  job,
  pending,
  canEdit,
  onEdit,
  onPublish,
  onClose,
  onArchive,
}: {
  job: Job;
  pending: boolean;
  canEdit: boolean;
  onEdit: () => void;
  onPublish: () => void;
  onClose: () => void;
  onArchive: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-xl font-semibold">{job.title}</h1>
            <JobStatusBadge status={job.status} />
          </div>
          <p className="text-xs text-muted-foreground">
            Created {formatDate(job.created_at)} · Updated {formatDate(job.updated_at)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canEdit ? (
            <Button size="sm" variant="outline" onClick={onEdit} disabled={pending}>
              Edit
            </Button>
          ) : null}
          <JobActions
            status={job.status}
            pending={pending}
            onPublish={onPublish}
            onClose={onClose}
            onArchive={onArchive}
          />
        </div>
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Details</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2">
            <Detail label="Location">{job.location}</Detail>
            <Detail label="Employment Type">
              {job.employment_type ? EMPLOYMENT_TYPE_LABELS[job.employment_type as EmploymentType] : null}
            </Detail>
            <Detail label="Work Mode">
              {job.work_mode ? WORK_MODE_LABELS[job.work_mode as WorkMode] : null}
            </Detail>
            <Detail label="Minimum Experience">
              {job.experience_min_years != null ? `${job.experience_min_years} years` : null}
            </Detail>
            <Detail label="Salary">{formatSalary(job)}</Detail>
            <Detail label="Openings">{job.openings ?? null}</Detail>
            <Detail label="Application Deadline">
              {job.application_deadline ? formatDate(job.application_deadline) : null}
            </Detail>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Description</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm whitespace-pre-line">{job.description}</p>
          {job.eligibility_criteria ? (
            <>
              <p className="mt-4 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Eligibility
              </p>
              <p className="text-sm whitespace-pre-line">{job.eligibility_criteria}</p>
            </>
          ) : null}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Required Skills ({job.skills.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {job.skills.length === 0 ? (
            <p className="text-sm text-muted-foreground/70">
              No skills added yet. Add at least one before publishing.
            </p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {job.skills.map((skill) => (
                <li
                  key={skill.skill_id}
                  className="inline-flex items-center gap-1.5 rounded-lg border px-2.5 py-1 text-sm"
                >
                  <span className="font-medium">{skill.skill_name}</span>
                  <span className="text-xs text-muted-foreground">
                    {skill.required_level} · {SKILL_IMPORTANCE_LABELS[skill.importance]}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
