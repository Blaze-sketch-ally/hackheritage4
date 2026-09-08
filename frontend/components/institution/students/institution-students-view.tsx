"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Inbox, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { approveLinkRequest, getIncomingLinkRequests, rejectLinkRequest } from "@/lib/institution-links";
import type { InstitutionLinkRequest } from "@/types/institution-link";
import { StudentDirectory } from "@/components/institution/students/student-directory";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; requests: InstitutionLinkRequest[] };

type InstitutionAction = "approve" | "reject";

const ACTION_COPY: Record<
  InstitutionAction,
  { title: string; description: string; confirm: string; destructive: boolean; done: string }
> = {
  approve: {
    title: "Approve this student?",
    description: "The student will become visible in your dashboard, department, and skill analytics.",
    confirm: "Approve",
    destructive: false,
    done: "Student approved.",
  },
  reject: {
    title: "Reject this request?",
    description: "The student can submit a new request later if needed.",
    confirm: "Reject",
    destructive: true,
    done: "Request rejected.",
  },
};

const RUNNERS: Record<InstitutionAction, (id: string) => Promise<InstitutionLinkRequest>> = {
  approve: approveLinkRequest,
  reject: rejectLinkRequest,
};

function formatDate(value: string | null): string {
  if (!value) return "Unknown date";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

function displayName(request: InstitutionLinkRequest): string {
  return request.student_name?.trim() || request.student_username?.trim() || "A student";
}

/**
 * Pending join requests (approve/reject) plus the full Student Directory
 * (search/filter/sort/paginate over linked students -- see
 * components/institution/students/student-directory.tsx). Unlinking a
 * student happens from the directory's detail page
 * (/institution/students/[studentId]), not here.
 */
export function InstitutionStudentsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  const [pending, setPending] = useState<{ id: string; action: InstitutionAction } | null>(null);
  const [confirming, setConfirming] = useState<{ id: string; action: InstitutionAction } | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getIncomingLinkRequests()
      .then(({ requests }) => {
        if (!cancelled) setState({ status: "ready", requests });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your students."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function runAction(id: string, action: InstitutionAction) {
    setConfirming(null);
    setPending({ id, action });
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await RUNNERS[action](id);
      setState((prev) =>
        prev.status === "ready"
          ? { ...prev, requests: prev.requests.map((r) => (r.id === id ? updated : r)) }
          : prev,
      );
      setActionSuccess(ACTION_COPY[action].done);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Something went wrong. Please try again.");
    } finally {
      setPending(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Institution Students</h1>
        <p className="text-sm text-muted-foreground">
          Review join requests and browse the students linked to your institution.
        </p>
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading your students…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {state.error.status === 401
                  ? "Your session has expired. Please sign in again."
                  : "Could not load your students."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status !== 401 ? (
              <Button variant="outline" size="sm" onClick={reload}>
                <RefreshCw className="size-3.5" /> Try again
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? (
        <PendingRequests
          requests={state.requests.filter((r) => r.status === "PENDING")}
          pending={pending}
          onApprove={(id) => setConfirming({ id, action: "approve" })}
          onReject={(id) => setConfirming({ id, action: "reject" })}
        />
      ) : null}

      <StudentDirectory />

      <ConfirmationDialog
        open={!!confirming}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={confirming ? ACTION_COPY[confirming.action].title : ""}
        description={confirming ? ACTION_COPY[confirming.action].description : undefined}
        confirmLabel={confirming ? ACTION_COPY[confirming.action].confirm : "Confirm"}
        destructive={confirming ? ACTION_COPY[confirming.action].destructive : false}
        loading={!!pending}
        onConfirm={() => confirming && runAction(confirming.id, confirming.action)}
      />
    </div>
  );
}

function PendingRequests({
  requests,
  pending,
  onApprove,
  onReject,
}: {
  requests: InstitutionLinkRequest[];
  pending: { id: string; action: InstitutionAction } | null;
  onApprove: (id: string) => void;
  onReject: (id: string) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Pending Requests</CardTitle>
      </CardHeader>
      <CardContent>
        {requests.length === 0 ? (
          <EmptyState
            icon={Inbox}
            title="No pending requests"
            description="Join requests from students will appear here."
          />
        ) : (
          <ul className="space-y-3">
            {requests.map((request) => (
              <li
                key={request.id}
                className="flex flex-col gap-3 rounded-lg border p-3 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="min-w-0">
                  <p className="truncate font-medium">{displayName(request)}</p>
                  {request.student_username ? (
                    <p className="truncate text-xs text-muted-foreground">@{request.student_username}</p>
                  ) : null}
                  <p className="text-xs text-muted-foreground">
                    Requested {formatDate(request.created_at)}
                  </p>
                </div>
                <div className="flex shrink-0 items-center gap-2">
                  <Button size="sm" onClick={() => onApprove(request.id)} disabled={pending?.id === request.id}>
                    Approve
                  </Button>
                  <Button
                    size="sm"
                    variant="ghost"
                    onClick={() => onReject(request.id)}
                    disabled={pending?.id === request.id}
                  >
                    Reject
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
