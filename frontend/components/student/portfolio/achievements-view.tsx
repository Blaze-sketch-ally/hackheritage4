"use client";

import { useEffect, useState } from "react";
import { ArrowUpRight, Pencil, Plus, Trash2, Trophy } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import {
  createAchievement,
  deleteAchievement,
  listAchievements,
  updateAchievement,
} from "@/lib/student/portfolio";
import { AchievementFormDialog } from "@/components/student/portfolio/achievement-form-dialog";
import {
  formatMonthYear,
  type AchievementInput,
  type StudentAchievement,
} from "@/types/student-portfolio";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; items: StudentAchievement[] };

function errText(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

export function AchievementsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<StudentAchievement | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<StudentAchievement | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listAchievements()
      .then(({ achievements }) => {
        if (!cancelled) setState({ status: "ready", items: achievements });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({ status: "error", message: errText(err, "Could not load your achievements.") });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function openAdd() {
    setEditing(null);
    setFormError(null);
    setFormOpen(true);
  }
  function openEdit(item: StudentAchievement) {
    setEditing(item);
    setFormError(null);
    setFormOpen(true);
  }

  async function handleSubmit(input: AchievementInput) {
    setSubmitting(true);
    setFormError(null);
    setSuccess(null);
    try {
      if (editing) {
        const updated = await updateAchievement(editing.id, input);
        setState((s) =>
          s.status === "ready"
            ? { ...s, items: s.items.map((a) => (a.id === updated.id ? updated : a)) }
            : s,
        );
        setSuccess(`Updated "${updated.title}".`);
      } else {
        const created = await createAchievement(input);
        setState((s) => (s.status === "ready" ? { ...s, items: [created, ...s.items] } : s));
        setSuccess(`Added "${created.title}".`);
      }
      setFormOpen(false);
    } catch (err) {
      setFormError(errText(err, "Could not save your achievement. Please try again."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await deleteAchievement(deleting.id);
      setState((s) =>
        s.status === "ready" ? { ...s, items: s.items.filter((a) => a.id !== deleting.id) } : s,
      );
      setSuccess(`Deleted "${deleting.title}".`);
      setDeleting(null);
    } catch {
      setDeleting(null);
    } finally {
      setDeleteBusy(false);
    }
  }

  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-semibold">Achievements</h1>
          <p className="text-sm text-muted-foreground">
            Awards, recognition, and milestones. Portfolio evidence only.
          </p>
        </div>
        {state.status === "ready" && state.items.length > 0 && (
          <Button onClick={openAdd}>
            <Plus className="size-4" /> Add achievement
          </Button>
        )}
      </div>

      <FormSuccess message={success} />

      {state.status === "loading" && <RowsSkeleton />}
      {state.status === "error" && (
        <ErrorState message={state.message} onRetry={() => {
            setState({ status: "loading" });
            setReloadKey((k) => k + 1);
          }} />
      )}

      {state.status === "ready" && state.items.length === 0 && (
        <EmptyState
          icon={Trophy}
          title="No achievements yet"
          description="Add an award or milestone to show on your portfolio."
          actionLabel="+ Add your first achievement"
          onAction={openAdd}
        />
      )}

      {state.status === "ready" && state.items.length > 0 && (
        <div className="flex flex-col gap-3">
          {state.items.map((item) => (
            <Card key={item.id}>
              <CardContent className="flex flex-wrap items-start justify-between gap-3 py-4">
                <div className="min-w-0 space-y-0.5">
                  <p className="font-medium">{item.title}</p>
                  <p className="text-xs text-muted-foreground">
                    {item.achievement_date && formatMonthYear(item.achievement_date)}
                    {item.achievement_date && item.issuing_organization && " · "}
                    {item.issuing_organization}
                  </p>
                  {item.description && (
                    <p className="text-sm text-muted-foreground">{item.description}</p>
                  )}
                  {item.url && (
                    <a
                      href={item.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-1 inline-flex items-center gap-1 text-xs text-foreground hover:underline"
                    >
                      <ArrowUpRight className="size-3" /> View
                    </a>
                  )}
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button variant="ghost" size="icon" aria-label="Edit" onClick={() => openEdit(item)}>
                    <Pencil className="size-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Delete"
                    className="text-destructive hover:text-destructive"
                    onClick={() => setDeleting(item)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <AchievementFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        achievement={editing}
        submitting={submitting}
        error={formError}
        onSubmit={handleSubmit}
      />

      <ConfirmationDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete "${deleting?.title ?? "this achievement"}"?`}
        description="This can't be undone."
        confirmLabel="Delete achievement"
        destructive
        loading={deleteBusy}
        onConfirm={handleDelete}
      />
    </div>
  );
}

function RowsSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-label="Loading achievements" aria-busy="true">
      {[0, 1].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2 py-4">
            <div className="h-4 w-1/2 rounded bg-muted" />
            <div className="h-3 w-1/3 rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
