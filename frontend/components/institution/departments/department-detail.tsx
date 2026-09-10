"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowLeft, GraduationCap, Pencil, Users } from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { ApiError } from "@/lib/api";
import { getInstitutionDepartment } from "@/lib/institution/departments";
import type { DepartmentDetail as DepartmentDetailData } from "@/types/institution-department";
import { DepartmentForm } from "@/components/institution/departments/department-form";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; department: DepartmentDetailData };

export function DepartmentDetail({ departmentId }: { departmentId: string }) {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getInstitutionDepartment(departmentId)
      .then((department) => {
        if (!cancelled) setState({ status: "ready", department });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this department."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [departmentId, reloadKey]);

  return (
    <div className="space-y-6">
      <Link
        href="/institution/departments"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground"
      >
        <ArrowLeft className="size-3.5" aria-hidden="true" /> Back to departments
      </Link>

      {state.status === "loading" ? <Loading label="Loading department…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={
            state.error.status === 404 ? "This department was not found." : state.error.message
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
        <Ready
          department={state.department}
          onEdit={() => setEditing(true)}
          onViewStudents={() =>
            router.push(`/institution/students?department=${encodeURIComponent(state.department.id)}`)
          }
        />
      ) : null}

      {state.status === "ready" ? (
        <DepartmentForm
          key={`${state.department.id}-${state.department.updated_at}`}
          open={editing}
          onOpenChange={setEditing}
          department={state.department}
          onSaved={(updated) => {
            setEditing(false);
            setState({ status: "ready", department: updated });
          }}
        />
      ) : null}
    </div>
  );
}

function Ready({
  department,
  onEdit,
  onViewStudents,
}: {
  department: DepartmentDetailData;
  onEdit: () => void;
  onViewStudents: () => void;
}) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-4 rounded-xl bg-card p-6 ring-1 ring-foreground/10 sm:flex-row sm:items-center">
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <h1 className="text-lg font-semibold">{department.name}</h1>
            <Badge variant={department.is_active ? "default" : "secondary"}>
              {department.is_active ? "Active" : "Inactive"}
            </Badge>
          </div>
          <p className="text-sm text-muted-foreground">
            {[department.code, department.description].filter(Boolean).join("  ·  ") || "No description yet."}
          </p>
        </div>
        <Button size="sm" variant="outline" onClick={onEdit}>
          <Pencil className="size-3.5" /> Edit
        </Button>
      </div>

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Students" value={department.student_count.toLocaleString()} icon={Users} accent="indigo" />
        <StatCard
          label="Placed"
          value={department.placed_count.toLocaleString()}
          icon={GraduationCap}
          accent="emerald"
        />
        <StatCard label="Unplaced" value={department.unplaced_count.toLocaleString()} icon={Users} accent="amber" />
        <StatCard
          label="Placement Rate"
          value={department.placement_rate != null ? `${department.placement_rate}%` : "—"}
          helperText={department.student_count === 0 ? "no students yet" : undefined}
          icon={GraduationCap}
          accent="violet"
        />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Internships</CardTitle>
        </CardHeader>
        <CardContent className="flex items-center justify-between">
          <div>
            <p className="text-2xl font-semibold tabular-nums">{department.internship_selected_count}</p>
            <p className="text-xs text-muted-foreground">students selected for an internship</p>
          </div>
        </CardContent>
      </Card>

      <div className="flex justify-end">
        <Button onClick={onViewStudents}>View students in this department</Button>
      </div>
    </div>
  );
}
