"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ArrowLeft, Inbox, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { Filters } from "@/components/common/filters";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { getTrainingApplications, updateTrainingApplicationStatus } from "@/lib/industry/training";
import { TrainingApplicantCard } from "@/components/industry/training/training-applicant-card";
import {
  TRAINING_APPLICATION_STATUS_LABELS,
  TRAINING_TRANSITION_LABELS,
  type IndustrySettableTrainingStatus,
  type TrainingApplication,
  type TrainingApplicationStatus,
} from "@/types/training-application";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; applications: TrainingApplication[] };

const FILTER_OPTIONS = [
  { value: "ALL", label: "All" },
  ...Object.entries(TRAINING_APPLICATION_STATUS_LABELS).map(([value, label]) => ({ value, label })),
];

export function TrainingApplicantsView({ trainingId }: { trainingId: string }) {
  const [statusFilter, setStatusFilter] = useState("ALL");
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [pendingId, setPendingId] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<{
    id: string;
    target: IndustrySettableTrainingStatus;
  } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getTrainingApplications(trainingId, {
      status: statusFilter === "ALL" ? undefined : (statusFilter as TrainingApplicationStatus),
    })
      .then(({ applications }) => {
        if (!cancelled) setState({ status: "ready", applications });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load applicants."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [trainingId, statusFilter, reloadKey]);

  async function runTransition(id: string, target: IndustrySettableTrainingStatus) {
    setConfirming(null);
    setPendingId(id);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await updateTrainingApplicationStatus(id, target);
      setState((s) =>
        s.status === "ready"
          ? { ...s, applications: s.applications.map((a) => (a.id === id ? updated : a)) }
          : s,
      );
      setActionSuccess(`Application moved to ${TRAINING_TRANSITION_LABELS[target]}.`);
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Link
          href={`/industry/training/${trainingId}`}
          className="flex w-fit items-center gap-1 text-sm text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-3.5" /> Back to training
        </Link>
        <Filters value={statusFilter} onChange={setStatusFilter} options={FILTER_OPTIONS} aria-label="Status" />
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

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
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
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
      ) : null}

      {state.status === "ready" && state.applications.length === 0 ? (
        <EmptyState
          icon={Inbox}
          title="No applicants yet"
          description="Students who register for this training will show up here."
        />
      ) : null}

      {state.status === "ready" && state.applications.length > 0 ? (
        <div className="grid gap-3 sm:grid-cols-2">
          {state.applications.map((application) => (
            <TrainingApplicantCard
              key={application.id}
              application={application}
              pending={pendingId === application.id}
              onPick={(target) => setConfirming({ id: application.id, target })}
            />
          ))}
        </div>
      ) : null}

      <ConfirmationDialog
        open={confirming !== null}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={confirming ? `${TRAINING_TRANSITION_LABELS[confirming.target]}?` : ""}
        confirmLabel={confirming ? TRAINING_TRANSITION_LABELS[confirming.target] : "Confirm"}
        destructive={confirming?.target === "REJECTED"}
        loading={pendingId !== null}
        onConfirm={() => confirming && runTransition(confirming.id, confirming.target)}
      />
    </div>
  );
}
