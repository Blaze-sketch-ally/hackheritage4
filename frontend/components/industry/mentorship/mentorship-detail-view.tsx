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
  archiveMentorshipOpportunity,
  closeMentorshipOpportunity,
  getMentorshipOpportunity,
  publishMentorshipOpportunity,
  updateMentorshipOpportunity,
} from "@/lib/industry/mentorship-opportunities";
import { MentorshipForm } from "@/components/industry/mentorship/mentorship-form";
import { MentorshipActions } from "@/components/industry/mentorship/mentorship-actions";
import { MentorshipStatusBadge } from "@/components/industry/mentorship/mentorship-status-badge";
import {
  MENTORSHIP_WORK_MODE_LABELS,
  type IndustryMentorship,
  type MentorshipCreate,
} from "@/types/industry-mentorship";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; mentorship: IndustryMentorship };

type LifecycleAction = "publish" | "close" | "archive";

const ACTION_COPY: Record<
  LifecycleAction,
  { title: string; description: string; confirm: string; destructive: boolean; done: string }
> = {
  publish: {
    title: "Publish this mentorship opportunity?",
    description: "Students will be able to see it.",
    confirm: "Publish",
    destructive: false,
    done: "Mentorship opportunity published.",
  },
  close: {
    title: "Close this mentorship opportunity?",
    description: "It stops accepting new interest. You can publish it again later.",
    confirm: "Close",
    destructive: false,
    done: "Mentorship opportunity closed.",
  },
  archive: {
    title: "Archive this mentorship opportunity?",
    description: "It's hidden from students and moved out of your active list. This can't be undone.",
    confirm: "Archive",
    destructive: true,
    done: "Mentorship opportunity archived.",
  },
};

const RUNNERS: Record<LifecycleAction, (id: string) => Promise<IndustryMentorship>> = {
  publish: publishMentorshipOpportunity,
  close: closeMentorshipOpportunity,
  archive: archiveMentorshipOpportunity,
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

export function MentorshipDetailView({
  mentorshipId,
  initialEdit = false,
}: {
  mentorshipId: string;
  initialEdit?: boolean;
}) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState(initialEdit);

  const [saving, setSaving] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  const [pendingAction, setPendingAction] = useState<LifecycleAction | null>(null);
  const [confirming, setConfirming] = useState<LifecycleAction | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getMentorshipOpportunity(mentorshipId)
      .then((mentorship) => {
        if (!cancelled) setState({ status: "ready", mentorship });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this mentorship opportunity."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [mentorshipId, reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function handleSave(data: MentorshipCreate) {
    setSaving(true);
    setFormError(null);
    try {
      const updated = await updateMentorshipOpportunity(mentorshipId, data);
      setState({ status: "ready", mentorship: updated });
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
      const updated = await RUNNERS[action](mentorshipId);
      setState({ status: "ready", mentorship: updated });
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
        href="/industry/mentorship"
        className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" /> All mentorship opportunities
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
                  ? "This mentorship opportunity doesn't exist or isn't yours."
                  : state.error.status === 401
                    ? "Your session has expired. Please sign in again."
                    : "Could not load this mentorship opportunity."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status === 404 ? (
              <Button variant="outline" size="sm" render={<Link href="/industry/mentorship" />}>
                Back to mentorship opportunities
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
              <h1 className="text-xl font-semibold">Edit Mentorship Opportunity</h1>
              <MentorshipForm
                mode="edit"
                initial={state.mentorship}
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
              mentorship={state.mentorship}
              pending={pendingAction !== null}
              canEdit={state.mentorship.status === "DRAFT" || state.mentorship.status === "PUBLISHED"}
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
          <Button variant="ghost" size="sm" onClick={() => router.push("/industry/mentorship")}>
            Done
          </Button>
        </p>
      ) : null}
    </div>
  );
}

function ReadView({
  mentorship,
  pending,
  canEdit,
  onEdit,
  onPublish,
  onClose,
  onArchive,
}: {
  mentorship: IndustryMentorship;
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
            <h1 className="text-xl font-semibold">{mentorship.title}</h1>
            <MentorshipStatusBadge status={mentorship.status} />
          </div>
          <p className="text-xs text-muted-foreground">
            Created {formatDate(mentorship.created_at)} · Updated {formatDate(mentorship.updated_at)}
          </p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          {canEdit ? (
            <Button size="sm" variant="outline" onClick={onEdit} disabled={pending}>
              Edit
            </Button>
          ) : null}
          <MentorshipActions
            status={mentorship.status}
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
            <Detail label="Location">{mentorship.location}</Detail>
            <Detail label="Work Mode">{MENTORSHIP_WORK_MODE_LABELS[mentorship.work_mode]}</Detail>
            <Detail label="Duration">{`${mentorship.duration_months} months`}</Detail>
            <Detail label="Capacity">{mentorship.capacity}</Detail>
            <Detail label="Start Date">
              {mentorship.start_date ? formatDate(mentorship.start_date) : null}
            </Detail>
            <Detail label="Application Deadline">
              {mentorship.application_deadline ? formatDate(mentorship.application_deadline) : null}
            </Detail>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Description</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-sm whitespace-pre-line">{mentorship.description}</p>
          {mentorship.eligibility_criteria ? (
            <>
              <p className="mt-4 text-xs font-medium tracking-wide text-muted-foreground uppercase">
                Eligibility
              </p>
              <p className="text-sm whitespace-pre-line">{mentorship.eligibility_criteria}</p>
            </>
          ) : null}
        </CardContent>
      </Card>
    </div>
  );
}
