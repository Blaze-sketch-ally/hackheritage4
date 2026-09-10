"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Ban, Briefcase, CheckCircle2, GraduationCap, Pencil, Users } from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { ApiError } from "@/lib/api";
import {
  getPlacementDrive,
  getPlacementDriveApplicants,
  getPlacementDriveStudents,
  updatePlacementDriveStatus,
} from "@/lib/institution/placements";
import {
  DRIVE_STATUS_LABELS,
  DRIVE_STATUS_TRANSITIONS,
  type DriveApplicant,
  type DriveStatus,
  type EligibleStudent,
  type PlacementDriveDetail as PlacementDriveDetailData,
} from "@/types/institution-placement";
import { PlacementDriveForm } from "@/components/institution/placements/placement-drive-form";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; drive: PlacementDriveDetailData };

function statusBadgeVariant(status: DriveStatus): "default" | "secondary" | "outline" | "destructive" {
  if (status === "OPEN" || status === "IN_PROGRESS") return "default";
  if (status === "COMPLETED") return "secondary";
  if (status === "CANCELLED") return "destructive";
  return "outline";
}

export function PlacementDriveDetail({ driveId }: { driveId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState(false);
  const [statusUpdating, setStatusUpdating] = useState<DriveStatus | null>(null);
  const [statusError, setStatusError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    getPlacementDrive(driveId)
      .then((drive) => {
        if (!cancelled) setState({ status: "ready", drive });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this placement drive."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [driveId, reloadKey]);

  async function handleStatusChange(next: DriveStatus) {
    setStatusError(null);
    setStatusUpdating(next);
    try {
      const updated = await updatePlacementDriveStatus(driveId, next);
      setState({ status: "ready", drive: updated });
    } catch (err) {
      setStatusError(err instanceof ApiError ? err.message : "Could not update the drive status.");
    } finally {
      setStatusUpdating(null);
    }
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Link
        href="/institution/placements"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden="true" /> Back to placement drives
      </Link>

      {state.status === "loading" ? <Loading label="Loading placement drive…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={state.error.status === 404 ? "This placement drive was not found." : state.error.message}
          onRetry={
            state.error.status !== 404 && state.error.status !== 401
              ? () => {
                  setState({ status: "loading" });
                  setReloadKey((k) => k + 1);
                }
              : undefined
          }
        />
      ) : null}

      {state.status === "ready" ? (
        <>
          <Ready
            drive={state.drive}
            onEdit={() => setEditing(true)}
            onStatusChange={handleStatusChange}
            statusUpdating={statusUpdating}
            statusError={statusError}
          />
          <PlacementDriveForm
            key={`${state.drive.id}-${state.drive.updated_at}`}
            open={editing}
            onOpenChange={setEditing}
            drive={state.drive}
            onSaved={(updated) => {
              setEditing(false);
              setState({ status: "ready", drive: updated });
            }}
          />
        </>
      ) : null}
    </div>
  );
}

function Ready({
  drive,
  onEdit,
  onStatusChange,
  statusUpdating,
  statusError,
}: {
  drive: PlacementDriveDetailData;
  onEdit: () => void;
  onStatusChange: (next: DriveStatus) => void;
  statusUpdating: DriveStatus | null;
  statusError: string | null;
}) {
  const [view, setView] = useState<"eligible" | "applicants">("eligible");
  const transitions = DRIVE_STATUS_TRANSITIONS[drive.status];
  const hasEligibilityCriteria =
    drive.eligible_department_names.length > 0 ||
    drive.eligible_batches.length > 0 ||
    drive.minimum_cgpa != null ||
    drive.eligible_skill_names.length > 0;

  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-xl bg-card p-6 ring-1 ring-foreground/10 sm:flex-row sm:items-start sm:justify-between">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-lg font-semibold">{drive.title}</h1>
            <Badge variant={statusBadgeVariant(drive.status)}>{DRIVE_STATUS_LABELS[drive.status]}</Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {drive.job_title ?? "Untitled job"}
            {drive.company_name ? ` · ${drive.company_name}` : ""}
            {drive.job_status && drive.job_status !== "PUBLISHED" ? ` · job is now ${drive.job_status}` : ""}
          </p>
          {drive.description ? <p className="text-sm">{drive.description}</p> : null}
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Button size="sm" variant="outline" onClick={onEdit}>
            <Pencil className="size-3.5" /> Edit
          </Button>
          {transitions.map((next) => (
            <Button
              key={next}
              size="sm"
              variant={next === "CANCELLED" ? "outline" : "default"}
              onClick={() => onStatusChange(next)}
              disabled={statusUpdating !== null}
            >
              {next === "CANCELLED" ? <Ban className="size-3.5" /> : <CheckCircle2 className="size-3.5" />}
              {statusUpdating === next ? "Updating..." : `Mark ${DRIVE_STATUS_LABELS[next]}`}
            </Button>
          ))}
        </div>
      </div>

      {statusError ? (
        <p className="rounded-md border border-destructive/30 bg-destructive/5 px-3 py-2 text-sm text-destructive">
          {statusError}
        </p>
      ) : null}

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Eligible Students" value={drive.eligible_count.toLocaleString()} icon={Users} accent="indigo" />
        <StatCard label="Applied" value={drive.applied_count.toLocaleString()} icon={Briefcase} accent="blue" />
        <StatCard
          label="Selected"
          value={drive.selected_count.toLocaleString()}
          icon={GraduationCap}
          accent="emerald"
        />
        <StatCard
          label="Deadline"
          value={drive.application_deadline ?? "—"}
          icon={Briefcase}
          accent="amber"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Eligibility Criteria</CardTitle>
        </CardHeader>
        <CardContent className="space-y-2 text-sm">
          {!hasEligibilityCriteria ? (
            <p className="text-muted-foreground">No restrictions — every student linked to your institution is eligible.</p>
          ) : (
            <>
              {drive.eligible_department_names.length > 0 ? (
                <p>
                  <span className="text-muted-foreground">Departments: </span>
                  {drive.eligible_department_names.join(", ")}
                </p>
              ) : null}
              {drive.eligible_batches.length > 0 ? (
                <p>
                  <span className="text-muted-foreground">Batches: </span>
                  {drive.eligible_batches.join(", ")}
                </p>
              ) : null}
              {drive.minimum_cgpa != null ? (
                <p>
                  <span className="text-muted-foreground">Minimum CGPA: </span>
                  {drive.minimum_cgpa}
                </p>
              ) : null}
              {drive.eligible_skill_names.length > 0 ? (
                <p>
                  <span className="text-muted-foreground">Required Skills: </span>
                  {drive.eligible_skill_names.join(", ")}
                </p>
              ) : null}
            </>
          )}
        </CardContent>
      </Card>

      <div className="flex gap-2">
        <Button size="sm" variant={view === "eligible" ? "default" : "outline"} onClick={() => setView("eligible")}>
          Eligible Students
        </Button>
        <Button size="sm" variant={view === "applicants" ? "default" : "outline"} onClick={() => setView("applicants")}>
          Applicants
        </Button>
      </div>

      {view === "eligible" ? <EligibleStudentsPanel driveId={drive.id} /> : <ApplicantsPanel driveId={drive.id} />}
    </div>
  );
}

function EligibleStudentsPanel({ driveId }: { driveId: string }) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "error"; error: ApiError }
    | { status: "ready"; students: EligibleStudent[] }
  >({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    getPlacementDriveStudents(driveId)
      .then(({ students }) => {
        if (!cancelled) setState({ status: "ready", students });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load eligible students."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [driveId]);

  if (state.status === "loading") return <Loading label="Loading students…" className="py-10" />;
  if (state.status === "error") return <ErrorState message={state.error.message} />;
  if (state.students.length === 0) {
    return (
      <EmptyState
        icon={Users}
        title="No students linked to your institution yet"
        description="Once students join your institution, they'll be evaluated against this drive's eligibility criteria."
      />
    );
  }

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Student</TableHead>
              <TableHead>Department</TableHead>
              <TableHead>Batch</TableHead>
              <TableHead className="text-right">CGPA</TableHead>
              <TableHead>Eligibility</TableHead>
              <TableHead>Application Status</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {state.students.map((student) => (
              <TableRow key={student.id}>
                <TableCell>
                  <p className="text-sm font-medium">{student.full_name?.trim() || student.username || "Unnamed student"}</p>
                  {student.username ? <p className="text-xs text-muted-foreground">@{student.username}</p> : null}
                </TableCell>
                <TableCell className="text-sm">{student.department}</TableCell>
                <TableCell className="text-sm tabular-nums">{student.batch ?? "—"}</TableCell>
                <TableCell className="text-right text-sm tabular-nums">
                  {student.cgpa != null ? student.cgpa.toFixed(1) : "—"}
                </TableCell>
                <TableCell>
                  {student.is_eligible ? (
                    <Badge variant="default">Eligible</Badge>
                  ) : (
                    <div className="space-y-1">
                      <Badge variant="outline">Not Eligible</Badge>
                      <p className="text-xs text-muted-foreground">{student.reasons.join("; ")}</p>
                    </div>
                  )}
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{student.application_status ?? "Has not applied"}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function ApplicantsPanel({ driveId }: { driveId: string }) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "error"; error: ApiError }
    | { status: "ready"; applicants: DriveApplicant[] }
  >({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    getPlacementDriveApplicants(driveId)
      .then(({ applicants }) => {
        if (!cancelled) setState({ status: "ready", applicants });
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
  }, [driveId]);

  if (state.status === "loading") return <Loading label="Loading applicants…" className="py-10" />;
  if (state.status === "error") return <ErrorState message={state.error.message} />;
  if (state.applicants.length === 0) {
    return (
      <EmptyState
        icon={Briefcase}
        title="No applicants yet"
        description="Eligible students who apply to this drive's job will show up here with their real application status."
      />
    );
  }

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Student</TableHead>
              <TableHead>Department</TableHead>
              <TableHead className="text-right">CGPA</TableHead>
              <TableHead>Status</TableHead>
              <TableHead>Applied</TableHead>
              <TableHead>Interview</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {state.applicants.map((applicant) => (
              <TableRow key={applicant.application_id}>
                <TableCell>
                  <p className="text-sm font-medium">
                    {applicant.full_name?.trim() || applicant.username || "Unnamed student"}
                  </p>
                  {applicant.username ? <p className="text-xs text-muted-foreground">@{applicant.username}</p> : null}
                </TableCell>
                <TableCell className="text-sm">{applicant.department}</TableCell>
                <TableCell className="text-right text-sm tabular-nums">
                  {applicant.cgpa != null ? applicant.cgpa.toFixed(1) : "—"}
                </TableCell>
                <TableCell>
                  <Badge variant={applicant.status === "SELECTED" ? "default" : "outline"}>{applicant.status}</Badge>
                </TableCell>
                <TableCell className="text-sm text-muted-foreground">{applicant.applied_at ?? "—"}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {applicant.interview
                    ? `${applicant.interview.status} · ${applicant.interview.mode} · ${applicant.interview.scheduled_at}`
                    : "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
