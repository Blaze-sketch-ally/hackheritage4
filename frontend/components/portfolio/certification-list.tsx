"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Plus, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { CertificationCard } from "@/components/portfolio/certification-card";
import { CertificationForm } from "@/components/portfolio/certification-form";
import { ApiError } from "@/lib/api";
import { deleteCertification, listMyCertifications } from "@/lib/student/portfolio";
import type { Certification } from "@/types/portfolio";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; certifications: Certification[] };

/** The student's own editable certification list -- self-fetching, used
 * by both /student/portfolio and /student/certifications, never a
 * second implementation for either route. Same shape as ProjectList. */
export function CertificationList() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [formMode, setFormMode] = useState<"none" | "create" | string>("none");

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { certifications } = await listMyCertifications();
        if (cancelled) return;
        setState({ status: "ready", certifications });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your certifications."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function refresh() {
    setFormMode("none");
    setReloadKey((k) => k + 1);
  }

  async function handleDelete(certificationId: string) {
    if (!window.confirm("Delete this certification? This cannot be undone.")) return;
    try {
      await deleteCertification(certificationId);
      setReloadKey((k) => k + 1);
    } catch (err) {
      window.alert(err instanceof ApiError ? err.message : "Could not delete this certification.");
    }
  }

  if (state.status === "loading") {
    return (
      <div className="h-40 animate-pulse rounded-lg bg-muted" aria-busy="true" aria-label="Loading certifications" />
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load your certifications.</p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setState({ status: "loading" });
              setReloadKey((k) => k + 1);
            }}
          >
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { certifications } = state;
  const editingCertification =
    formMode !== "none" && formMode !== "create" ? certifications.find((c) => c.id === formMode) : undefined;

  return (
    <div className="space-y-4">
      {formMode === "create" && <CertificationForm onSaved={refresh} onCancel={() => setFormMode("none")} />}
      {editingCertification && (
        <CertificationForm certification={editingCertification} onSaved={refresh} onCancel={() => setFormMode("none")} />
      )}

      {formMode === "none" && (
        <>
          {certifications.length === 0 ? (
            <Card>
              <CardContent className="flex flex-col items-center gap-3 py-10 text-center text-muted-foreground">
                <p>Add certifications that strengthen your professional profile.</p>
                <Button size="sm" onClick={() => setFormMode("create")}>
                  <Plus className="size-3.5" /> Add Certification
                </Button>
              </CardContent>
            </Card>
          ) : (
            <>
              <div className="flex justify-end">
                <Button size="sm" onClick={() => setFormMode("create")}>
                  <Plus className="size-3.5" /> Add Certification
                </Button>
              </div>
              <div className="grid gap-4 sm:grid-cols-2">
                {certifications.map((certification) => (
                  <CertificationCard
                    key={certification.id}
                    certification={certification}
                    onEdit={() => setFormMode(certification.id)}
                    onDelete={() => handleDelete(certification.id)}
                  />
                ))}
              </div>
            </>
          )}
        </>
      )}
    </div>
  );
}
