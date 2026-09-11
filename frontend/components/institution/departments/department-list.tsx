"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, Plus, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { ApiError } from "@/lib/api";
import { getInstitutionDepartments } from "@/lib/institution/departments";
import { toast } from "@/components/ui/sonner";
import type { DepartmentSummary } from "@/types/institution-department";
import { DepartmentForm } from "@/components/institution/departments/department-form";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; departments: DepartmentSummary[] };

type StatusFilter = "all" | "active" | "inactive";

export function DepartmentList() {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<StatusFilter>("all");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<DepartmentSummary | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    getInstitutionDepartments()
      .then(({ departments }) => {
        if (!cancelled) setState({ status: "ready", departments });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your departments."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const filtered = useMemo(() => {
    if (state.status !== "ready") return [];
    let rows = state.departments;
    if (statusFilter !== "all") {
      rows = rows.filter((d) => (statusFilter === "active" ? d.is_active : !d.is_active));
    }
    const needle = search.trim().toLowerCase();
    if (needle) {
      rows = rows.filter(
        (d) => d.name.toLowerCase().includes(needle) || (d.code ?? "").toLowerCase().includes(needle),
      );
    }
    return rows;
  }, [state, search, statusFilter]);

  function openCreate() {
    setEditing(undefined);
    setFormOpen(true);
  }

  function openEdit(department: DepartmentSummary) {
    setEditing(department);
    setFormOpen(true);
  }

  function handleSaved() {
    setFormOpen(false);
    toast.success(editing ? "Department updated successfully!" : "Department created successfully!");
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  const hasAnyDepartments = state.status === "ready" && state.departments.length > 0;

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Departments</h1>
          <p className="text-sm text-muted-foreground">
            Departments organize your institution&apos;s students and placement analytics.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="size-4" /> Add Department
        </Button>
      </div>

      {hasAnyDepartments ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by name or code..."
              className="pl-8"
              aria-label="Search departments"
            />
          </div>
          <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v as StatusFilter)}>
            <SelectTrigger className="w-full sm:w-40" aria-label="Status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="all">All statuses</SelectItem>
              <SelectItem value="active">Active</SelectItem>
              <SelectItem value="inactive">Inactive</SelectItem>
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {state.status === "loading" ? <Loading label="Loading departments…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={state.error.message}
          onRetry={() => {
            setState({ status: "loading" });
            setReloadKey((k) => k + 1);
          }}
        />
      ) : null}

      {state.status === "ready" ? (
        state.departments.length === 0 ? (
          <EmptyState
            icon={Building2}
            title="No departments yet"
            description="Add your first department to start organizing students and placement analytics."
            actionLabel="Add Department"
            onAction={openCreate}
          />
        ) : filtered.length === 0 ? (
          <EmptyState
            icon={Search}
            title="No departments match your filters"
            description="Try a different search term or clear the status filter."
          />
        ) : (
          <Card>
            <CardContent className="p-0">
              <div className="overflow-x-auto">
                <Table className="min-w-[700px]">
                  <TableHeader>
                    <TableRow>
                      <TableHead>Department</TableHead>
                      <TableHead>Code</TableHead>
                      <TableHead className="text-right">Students</TableHead>
                      <TableHead className="text-right">Placed</TableHead>
                      <TableHead className="text-right">Unplaced</TableHead>
                      <TableHead className="text-right">Placement %</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((d) => (
                      <TableRow key={d.id}>
                        <TableCell
                          className="cursor-pointer font-medium hover:underline"
                          onClick={() => router.push(`/institution/departments/${d.id}`)}
                        >
                          {d.name}
                        </TableCell>
                        <TableCell className="text-muted-foreground">{d.code ?? "—"}</TableCell>
                        <TableCell className="text-right tabular-nums">{d.student_count}</TableCell>
                        <TableCell className="text-right tabular-nums">{d.placed_count}</TableCell>
                        <TableCell className="text-right tabular-nums">{d.unplaced_count}</TableCell>
                        <TableCell className="text-right tabular-nums">
                          {d.placement_rate != null ? `${d.placement_rate}%` : "—"}
                        </TableCell>
                        <TableCell>
                          <Badge variant={d.is_active ? "default" : "secondary"}>
                            {d.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button size="sm" variant="outline" onClick={() => openEdit(d)}>
                            Edit
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </div>
            </CardContent>
          </Card>
        )
      ) : null}

      <DepartmentForm
        key={editing?.id ?? "create"}
        open={formOpen}
        onOpenChange={setFormOpen}
        department={editing}
        onSaved={handleSaved}
      />
    </div>
  );
}
