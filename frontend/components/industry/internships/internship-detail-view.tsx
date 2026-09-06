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
  archiveInternship,
  closeInternship,
  getInternship,
  publishInternship,
  updateInternship,
} from "@/lib/industry/internships";
import { getSkillCatalog, type CatalogSkill } from "@/lib/industry/skills";
import { InternshipForm } from "@/components/industry/opportunity-form";
import { InternshipActions } from "@/components/industry/internships/internship-actions";
import { InternshipProgramLink } from "@/components/industry/internship-program/internship-program-link";
import { InternshipStatusBadge } from "@/components/industry/internships/internship-status-badge";
import {
  SKILL_IMPORTANCE_LABELS,
  WORK_MODE_LABELS,
  type Internship,
  type InternshipCreate,
  type WorkMode,
} from "@/types/internship";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; internship: Internship };

type LifecycleAction = "publish" | "close" | "archive";

const ACTION_COPY: Record<
  LifecycleAction,
  { title: string; description: string; confirm: string; destructive: boolean; done: string }
> = {
  publish: {
    title: "Publish this internship?",
    description: "Students will be able to see and apply to it.",
    confirm: "Publish",
    destructive: false,
    done: "Internship published.",
  },
  close: {
    title: "Close this internship?",
    description: "It stops accepting new applications. You can publish it again later.",
    confirm: "Close",
    destructive: false,
    done: "Internship closed.",
  },
  archive: {
    title: "Archive this internship?",
    description: "It's hidden from students and moved out of your active list. This can't be undone.",
    confirm: "Archive",
    destructive: true,
    done: "Internship archived.",
  },
};

const RUNNERS: Record<LifecycleAction, (id: string) => Promise<Internship>> = {
  publish: publishInternship,
  close: closeInternship,
  archive: archiveInternship,
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

export function InternshipDetailView({
  internshipId,
  initialEdit = false,
}: {
  internshipId: string;
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
    getInternship(internshipId)
      .then((internship) => {
        if (!cancelled) setState({ status: "ready", internship });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this internship."),
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
  }, [internshipId, reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function handleSave(data: InternshipCreate) {
    setSaving(true);
    setFormError(null);
    try {
      const updated = await updateInternship(internshipId, data);
      setState({ status: "ready", internship: updated });
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
      const updated = await RUNNERS[action](internshipId);
      setState({ status: "ready", internship: updated });
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
        href="/industry/internships"
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> All internships
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
                  ? "This internship doesn't exist or isn't yours."
                  : state.error.status === 401
                    ? "Your session has expired. Please sign in again."
                    : "Could not load this internship."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status === 404 ? (
              <Button variant="outline" size="sm" render={<Link href="/industry/internships" />}>
                Back to internships
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
              <h1 className="text-xl font-semibold">Edit Internship</h1>
              <InternshipForm
                mode="edit"
                catalog={catalog}
                initial={state.internship}
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
              internship={state.internship}
              pending={pendingAction !== null}
              canEdit={state.internship.status === "DRAFT" || state.internship.status === "PUBLISHED"}
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
          <Button variant="ghost" size="sm" onClick={() => router.push("/industry/internships")}>
            Done
          </Button>
        </p>
      ) : null}
    </div>
  );
}

function ReadView({
  internship,
  pending,
  canEdit,
  onEdit,
  onPublish,
  onClose,
  onArchive,
}: {
  internship: Internship;
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
            <h1 className="text-xl font-semibold">{internship.title}</h1>
            <InternshipStatusBadge status={internship.status} />
          </div>
          <p className="text-xs text-muted-foreground">
            Created {formatDate(internship.created_at)} · Updated {formatDate(internship.updated_at)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canEdit ? (
            <Button size="sm" variant="outline" onClick={onEdit} disabled={pending}>
              Edit
            </Button>
          ) : null}
          <InternshipActions
            status={internship.status}
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
            <Detail label="Location">{internship.location}</Detail>
            <Detail label="Work Mode">
              {internship.work_mode ? WORK_MODE_LABELS[internship.work_mode as WorkMode] : null}
            </Detail>
            <Detail label="Duration">
              {internship.duration_months ? `${internship.duration_months} months` : null}
            </Detail>
            <Detail label="Openings">{internship.openings ?? null}</Detail>
            <Detail label="Monthly Stipend">
              {internship.stipend_amount != null
                ? `${internship.stipend_currency ?? "INR"} ${internship.stipend_amount.toLocaleString()}`
                : null}
            </Detail>
            <Detail label="Application Deadline">
              {internship.application_deadline ? formatDate(internship.application_deadline) : null}
            </Detail>
            <Detail label="Start Date">
              {internship.start_date ? formatDate(internship.start_date) : null}
            </Detail>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Description</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm whitespace-pre-line">{internship.description}</p>
          {internship.eligibility_criteria ? (
            <>
              <p className="mt-4 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Eligibility
              </p>
              <p className="text-sm whitespace-pre-line">{internship.eligibility_criteria}</p>
            </>
          ) : null}
        </CardContent>
      </Card>

      <InternshipProgramLink internshipId={internship.id} />

      <Card>
        <CardHeader>
          <CardTitle>Required Skills ({internship.skills.length})</CardTitle>
        </CardHeader>
        <CardContent>
          {internship.skills.length === 0 ? (
            <p className="text-sm text-muted-foreground/70">
              No skills added yet. Add at least one before publishing.
            </p>
          ) : (
            <ul className="flex flex-wrap gap-2">
              {internship.skills.map((skill) => (
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
