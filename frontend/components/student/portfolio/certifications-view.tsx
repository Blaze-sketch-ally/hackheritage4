"use client";

import { useEffect, useState } from "react";
import { Award, ArrowUpRight, Pencil, Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import {
  createCertification,
  deleteCertification,
  listCertifications,
  updateCertification,
} from "@/lib/student/portfolio";
import { CertificationFormDialog } from "@/components/student/portfolio/certification-form-dialog";
import {
  formatMonthYear,
  type CertificationInput,
  type StudentCertification,
} from "@/types/student-portfolio";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; items: StudentCertification[] };

function errText(err: unknown, fallback: string) {
  return err instanceof ApiError ? err.message : fallback;
}

export function CertificationsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<StudentCertification | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);
  const [deleting, setDeleting] = useState<StudentCertification | null>(null);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [success, setSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    listCertifications()
      .then(({ certifications }) => {
        if (!cancelled) setState({ status: "ready", items: certifications });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({ status: "error", message: errText(err, "Could not load your certifications.") });
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
  function openEdit(item: StudentCertification) {
    setEditing(item);
    setFormError(null);
    setFormOpen(true);
  }

  async function handleSubmit(input: CertificationInput) {
    setSubmitting(true);
    setFormError(null);
    setSuccess(null);
    try {
      if (editing) {
        const updated = await updateCertification(editing.id, input);
        setState((s) =>
          s.status === "ready"
            ? { ...s, items: s.items.map((c) => (c.id === updated.id ? updated : c)) }
            : s,
        );
        setSuccess(`Updated "${updated.name}".`);
      } else {
        const created = await createCertification(input);
        setState((s) => (s.status === "ready" ? { ...s, items: [created, ...s.items] } : s));
        setSuccess(`Added "${created.name}".`);
      }
      setFormOpen(false);
    } catch (err) {
      setFormError(errText(err, "Could not save your certification. Please try again."));
    } finally {
      setSubmitting(false);
    }
  }

  async function handleDelete() {
    if (!deleting) return;
    setDeleteBusy(true);
    try {
      await deleteCertification(deleting.id);
      setState((s) =>
        s.status === "ready" ? { ...s, items: s.items.filter((c) => c.id !== deleting.id) } : s,
      );
      setSuccess(`Deleted "${deleting.name}".`);
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
          <h1 className="text-xl font-semibold">Certifications</h1>
          <p className="text-sm text-muted-foreground">
            Credentials you&apos;ve earned. Portfolio evidence only — not a skill verification.
          </p>
        </div>
        {state.status === "ready" && state.items.length > 0 && (
          <Button onClick={openAdd}>
            <Plus className="size-4" /> Add certification
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
          icon={Award}
          title="No certifications yet"
          description="Add a certification to show on your portfolio."
          actionLabel="+ Add your first certification"
          onAction={openAdd}
        />
      )}

      {state.status === "ready" && state.items.length > 0 && (
        <div className="flex flex-col gap-3">
          {state.items.map((cert) => (
            <Card key={cert.id}>
              <CardContent className="flex flex-wrap items-start justify-between gap-3 py-4">
                <div className="min-w-0 space-y-0.5">
                  <p className="font-medium">{cert.name}</p>
                  {cert.issuing_organization && (
                    <p className="text-sm text-muted-foreground">{cert.issuing_organization}</p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    {cert.issue_date && `Issued ${formatMonthYear(cert.issue_date)}`}
                    {cert.issue_date && cert.expiry_date && " · "}
                    {cert.expiry_date && `Expires ${formatMonthYear(cert.expiry_date)}`}
                    {cert.credential_id && ` · ID ${cert.credential_id}`}
                  </p>
                  {cert.credential_url && (
                    <a
                      href={cert.credential_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="mt-1 inline-flex items-center gap-1 text-xs text-foreground hover:underline"
                    >
                      <ArrowUpRight className="size-3" /> View credential
                    </a>
                  )}
                </div>
                <div className="flex shrink-0 gap-1">
                  <Button variant="ghost" size="icon" aria-label="Edit" onClick={() => openEdit(cert)}>
                    <Pencil className="size-4" />
                  </Button>
                  <Button
                    variant="ghost"
                    size="icon"
                    aria-label="Delete"
                    className="text-destructive hover:text-destructive"
                    onClick={() => setDeleting(cert)}
                  >
                    <Trash2 className="size-4" />
                  </Button>
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <CertificationFormDialog
        open={formOpen}
        onOpenChange={setFormOpen}
        certification={editing}
        submitting={submitting}
        error={formError}
        onSubmit={handleSubmit}
      />

      <ConfirmationDialog
        open={!!deleting}
        onOpenChange={(open) => !open && setDeleting(null)}
        title={`Delete "${deleting?.name ?? "this certification"}"?`}
        description="This can't be undone."
        confirmLabel="Delete certification"
        destructive
        loading={deleteBusy}
        onConfirm={handleDelete}
      />
    </div>
  );
}

function RowsSkeleton() {
  return (
    <div className="flex flex-col gap-3" aria-label="Loading certifications" aria-busy="true">
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
