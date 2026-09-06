"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Award,
  Briefcase,
  CalendarClock,
  ExternalLink,
  FolderGit2,
  Info,
  UserMinus,
} from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { FormError } from "@/components/auth/form-error";
import { ApiError } from "@/lib/api";
import { getInstitutionStudent } from "@/lib/institution/students";
import { unlinkStudent } from "@/lib/institution-links";
import {
  INTERNSHIP_STATUS_LABELS,
  PLACEMENT_STATUS_LABELS,
  type StudentDetail,
} from "@/types/institution-student";
import { DepartmentAssignment } from "@/components/institution/students/department-assignment";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; student: StudentDetail };

function initials(name: string | null): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return "?";
}

function formatDate(value: string | null): string {
  if (!value) return "Unknown date";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Date(parsed).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

export function StudentDetailView({ studentId }: { studentId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [confirmingUnlink, setConfirmingUnlink] = useState(false);
  const [unlinking, setUnlinking] = useState(false);
  const [actionError, setActionError] = useState<string | null>(null);
  const [unlinked, setUnlinked] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getInstitutionStudent(studentId)
      .then((student) => {
        if (!cancelled) setState({ status: "ready", student });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this student."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [studentId, reloadKey]);

  async function handleUnlink() {
    if (state.status !== "ready" || !state.student.link_request_id) return;
    setUnlinking(true);
    setActionError(null);
    try {
      await unlinkStudent(state.student.link_request_id);
      setConfirmingUnlink(false);
      setUnlinked(true);
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not unlink this student.");
    } finally {
      setUnlinking(false);
    }
  }

  return (
    <div className="space-y-6">
      <Link
        href="/institution/students"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden="true" /> Back to students
      </Link>

      {state.status === "loading" ? <Loading label="Loading student…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={
            state.error.status === 404
              ? "This student was not found, or is not linked to your institution."
              : state.error.message
          }
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
        unlinked ? (
          <EmptyState
            icon={UserMinus}
            title="Student unlinked"
            description="This student is no longer linked to your institution."
          />
        ) : (
          <Ready
            student={state.student}
            actionError={actionError}
            onRequestUnlink={() => setConfirmingUnlink(true)}
            onStudentUpdated={(updated) => setState({ status: "ready", student: updated })}
          />
        )
      ) : null}

      <ConfirmationDialog
        open={confirmingUnlink}
        onOpenChange={setConfirmingUnlink}
        title="Unlink this student?"
        description="They will no longer be counted in your dashboard, department, or skill analytics. They may request to join again later."
        confirmLabel="Unlink"
        destructive
        loading={unlinking}
        onConfirm={handleUnlink}
      />
    </div>
  );
}

function Ready({
  student,
  actionError,
  onRequestUnlink,
  onStudentUpdated,
}: {
  student: StudentDetail;
  actionError: string | null;
  onRequestUnlink: () => void;
  onStudentUpdated: (student: StudentDetail) => void;
}) {
  return (
    <div className="space-y-6">
      <FormError message={actionError} />

      <div className="flex flex-col gap-4 rounded-xl bg-card p-6 ring-1 ring-foreground/10 sm:flex-row sm:items-center">
        <Avatar className="size-16">
          <AvatarImage src={student.avatar_url ?? undefined} alt="" />
          <AvatarFallback className="text-lg">{initials(student.full_name)}</AvatarFallback>
        </Avatar>
        <div className="min-w-0 flex-1 space-y-1 text-center sm:text-left">
          <h1 className="truncate text-lg font-semibold">
            {student.full_name?.trim() || student.username || "Unnamed student"}
          </h1>
          <p className="text-sm text-muted-foreground">
            {[student.department, student.batch ? `Batch ${student.batch}` : null, student.degree]
              .filter(Boolean)
              .join("  ·  ") || "Profile incomplete"}
          </p>
        </div>
        <div className="flex flex-col items-center gap-2 sm:items-end">
          <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400">
            {student.profile_completion}% profile complete
          </span>
          {student.link_request_id ? (
            <Button size="sm" variant="ghost" onClick={onRequestUnlink}>
              <UserMinus className="size-3.5" /> Unlink student
            </Button>
          ) : null}
        </div>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <AcademicsCard student={student} onStudentUpdated={onStudentUpdated} />
        <SkillsCard student={student} />
      </div>

      <PortfolioCard student={student} />
      <ApplicationsCard student={student} />

      <div className="grid gap-6 lg:grid-cols-2">
        <AssessmentsCard student={student} />
        <InterviewsCard student={student} />
      </div>

      {student.notes.length > 0 ? (
        <div className="space-y-2">
          {student.notes.map((note) => (
            <p
              key={note}
              className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground"
            >
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              {note}
            </p>
          ))}
        </div>
      ) : null}
    </div>
  );
}

function AcademicsCard({
  student,
  onStudentUpdated,
}: {
  student: StudentDetail;
  onStudentUpdated: (student: StudentDetail) => void;
}) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Academics &amp; Placement</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <DepartmentAssignment student={student} onStudentUpdated={onStudentUpdated} />
        <div className="grid grid-cols-2 gap-3">
          <Stat label="CGPA" value={student.cgpa != null ? student.cgpa.toFixed(2) : "—"} />
          <Stat label="Percentage" value={student.percentage != null ? `${student.percentage}%` : "—"} />
          <Stat label="Placement" value={PLACEMENT_STATUS_LABELS[student.placement_status]} />
          <Stat label="Internship" value={INTERNSHIP_STATUS_LABELS[student.internship_status]} />
        </div>
      </CardContent>
    </Card>
  );
}

function Stat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-muted/50 px-3 py-2">
      <p className="text-lg font-semibold tabular-nums">{value}</p>
      <p className="text-[11px] text-muted-foreground">{label}</p>
    </div>
  );
}

function SkillsCard({ student }: { student: StudentDetail }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Skills</CardTitle>
      </CardHeader>
      <CardContent>
        {student.skills.length === 0 ? (
          <EmptyState title="No skills recorded yet" />
        ) : (
          <ul className="flex flex-wrap gap-2">
            {student.skills.map((skill) => (
              <li key={skill.skill_name}>
                <Badge variant={skill.is_verified ? "default" : "outline"}>
                  {skill.skill_name} · {skill.proficiency_level}
                  {skill.is_verified ? " ✓" : ""}
                </Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function PortfolioCard({ student }: { student: StudentDetail }) {
  const hasAny =
    student.projects.length > 0 || student.certifications.length > 0 || student.achievements.length > 0;

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Projects &amp; Portfolio</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        {!hasAny ? (
          <EmptyState icon={FolderGit2} title="No portfolio items yet" />
        ) : (
          <>
            {student.projects.map((project) => (
              <div key={project.id} className="space-y-1 border-b pb-3 last:border-0 last:pb-0">
                <div className="flex flex-wrap items-center gap-2">
                  <p className="font-medium">{project.title}</p>
                  {project.is_ongoing ? <Badge variant="secondary">Ongoing</Badge> : null}
                </div>
                {project.description ? (
                  <p className="text-sm text-muted-foreground">{project.description}</p>
                ) : null}
                <div className="flex flex-wrap gap-1">
                  {project.skills.map((s) => (
                    <Badge key={s} variant="outline" className="text-[10px]">
                      {s}
                    </Badge>
                  ))}
                </div>
                <div className="flex gap-3 text-xs">
                  {project.project_url ? (
                    <ExternalLinkText href={project.project_url} label="Live" />
                  ) : null}
                  {project.repo_url ? <ExternalLinkText href={project.repo_url} label="Repo" /> : null}
                </div>
              </div>
            ))}

            {student.certifications.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  Certifications
                </p>
                <ul className="space-y-1.5">
                  {student.certifications.map((c) => (
                    <li key={c.id} className="flex items-center gap-1.5 text-sm">
                      <Award className="size-3.5 shrink-0 text-amber-600 dark:text-amber-400" aria-hidden="true" />
                      {c.name}
                      {c.issuing_organization ? (
                        <span className="text-muted-foreground"> · {c.issuing_organization}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}

            {student.achievements.length > 0 ? (
              <div className="space-y-2">
                <p className="text-xs font-medium tracking-wide text-muted-foreground uppercase">
                  Achievements
                </p>
                <ul className="space-y-1.5">
                  {student.achievements.map((a) => (
                    <li key={a.id} className="text-sm">
                      {a.title}
                      {a.issuing_organization ? (
                        <span className="text-muted-foreground"> · {a.issuing_organization}</span>
                      ) : null}
                    </li>
                  ))}
                </ul>
              </div>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}

function ExternalLinkText({ href, label }: { href: string; label: string }) {
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-indigo-600 hover:underline dark:text-indigo-400"
    >
      {label} <ExternalLink className="size-3 shrink-0" aria-hidden="true" />
    </a>
  );
}

function ApplicationsCard({ student }: { student: StudentDetail }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Applications</CardTitle>
      </CardHeader>
      <CardContent>
        {student.applications.length === 0 ? (
          <EmptyState icon={Briefcase} title="No applications yet" />
        ) : (
          <ul className="divide-y">
            {student.applications.map((app) => (
              <li key={app.id} className="flex items-center justify-between gap-3 py-2.5 first:pt-0 last:pb-0">
                <div className="min-w-0">
                  <p className="truncate text-sm font-medium">{app.opportunity_title ?? "Untitled posting"}</p>
                  <p className="truncate text-xs text-muted-foreground">
                    {app.company_name ?? "Unknown company"} ·{" "}
                    <Badge variant="outline" className="align-middle text-[10px]">
                      {app.opportunity_type === "JOB" ? "Job" : "Internship"}
                    </Badge>{" "}
                    · Applied {formatDate(app.applied_at)}
                  </p>
                </div>
                <Badge variant={app.status === "SELECTED" ? "default" : "secondary"}>{app.status}</Badge>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function AssessmentsCard({ student }: { student: StudentDetail }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Assessments</CardTitle>
        <p className="text-xs text-muted-foreground">
          {student.assessments_completed} completed
          {student.average_assessment_percentage != null
            ? `, averaging ${student.average_assessment_percentage}%`
            : ""}
          .
        </p>
      </CardHeader>
      <CardContent>
        {student.assessments.length === 0 ? (
          <EmptyState title="No assessments taken yet" />
        ) : (
          <ul className="space-y-2">
            {student.assessments.map((a, i) => (
              <li key={i} className="flex items-center justify-between gap-3 text-sm">
                <span className="min-w-0 truncate">
                  {a.assessment_title ?? "Untitled assessment"}
                  {a.skill_name ? <span className="text-muted-foreground"> · {a.skill_name}</span> : null}
                </span>
                <span className="shrink-0 tabular-nums text-muted-foreground">
                  {a.percentage != null ? `${a.percentage}%` : a.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}

function InterviewsCard({ student }: { student: StudentDetail }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Interviews</CardTitle>
      </CardHeader>
      <CardContent>
        {student.interviews.length === 0 ? (
          <EmptyState icon={CalendarClock} title="No interviews on record" />
        ) : (
          <ul className="space-y-2">
            {student.interviews.map((iv) => (
              <li key={iv.id} className="flex items-center justify-between gap-3 text-sm">
                <span className="min-w-0 truncate">
                  {iv.opportunity_title ?? "Untitled posting"}
                  <span className="text-muted-foreground"> · {iv.mode}</span>
                </span>
                <span className="shrink-0 text-xs text-muted-foreground">
                  {formatDate(iv.scheduled_at)} · {iv.status}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
