"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { ArrowDown, ArrowUp, GraduationCap, Search, Users } from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { ApiError } from "@/lib/api";
import { getInstitutionStudents } from "@/lib/institution/students";
import {
  PLACEMENT_STATUS_LABELS,
  INTERNSHIP_STATUS_LABELS,
  UNASSIGNED_DEPARTMENT_FILTER,
  type InternshipStatus,
  type PlacementStatus,
  type StudentListParams,
  type StudentListResponse,
  type StudentSummary,
} from "@/types/institution-student";

const ALL = "__all__";
const PAGE_SIZE = 20;

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; data: StudentListResponse };

type SortBy = NonNullable<StudentListParams["sort_by"]>;

function initials(name: string | null): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return "?";
}

function placementBadgeVariant(status: PlacementStatus): "default" | "secondary" | "outline" {
  if (status === "PLACED") return "default";
  if (status === "APPLYING") return "secondary";
  return "outline";
}

function internshipBadgeVariant(status: InternshipStatus): "default" | "secondary" | "outline" {
  if (status === "SELECTED") return "default";
  if (status === "APPLYING") return "secondary";
  return "outline";
}

/**
 * The Student Directory: search/filter/sort/paginate over students
 * LINKED to this institution (student_profiles.institution_id), backed
 * by GET /api/v1/institution/students. Summary cards and per-student
 * placement/internship status reuse the exact same computation as the
 * Institution Dashboard -- never a second definition of "placed".
 */
export function StudentDirectory() {
  const router = useRouter();
  const searchParams = useSearchParams();
  // Supports linking in from elsewhere (e.g. the department detail page's
  // "View students" button, or the Internships page's "View selected
  // students" link) as /institution/students?department=<id> and/or
  // ?internship_status=SELECTED -- read once on mount, same as any other
  // initial-state derivation.
  const initialDepartment = searchParams.get("department") ?? ALL;
  const initialInternshipStatus = searchParams.get("internship_status") ?? ALL;

  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [department, setDepartment] = useState<string>(initialDepartment);
  const [batch, setBatch] = useState<string>(ALL);
  const [placementStatus, setPlacementStatus] = useState<string>(ALL);
  const [internshipStatus, setInternshipStatus] = useState<string>(initialInternshipStatus);
  const [skill, setSkill] = useState("");
  const [debouncedSkill, setDebouncedSkill] = useState("");
  const [sortBy, setSortBy] = useState<SortBy>("name");
  const [sortDir, setSortDir] = useState<"asc" | "desc">("asc");
  const [page, setPage] = useState(1);

  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  // Debounced values reset the page to 1 inside the same timeout callback
  // (not synchronously in the effect body) -- a narrower result set could
  // otherwise leave the user stranded on a page that no longer exists.
  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSearch(search);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    const timer = setTimeout(() => {
      setDebouncedSkill(skill);
      setPage(1);
    }, 300);
    return () => clearTimeout(timer);
  }, [skill]);

  // Non-debounced filters (selects) reset the page directly in their own
  // onChange handler below -- see `updateFilter`.
  function updateFilter<T>(setter: (value: T) => void) {
    return (value: T) => {
      setter(value);
      setPage(1);
    };
  }

  const params: StudentListParams = useMemo(
    () => ({
      search: debouncedSearch || undefined,
      department: department === ALL ? undefined : department,
      batch: batch === ALL ? undefined : Number(batch),
      placement_status: placementStatus === ALL ? undefined : (placementStatus as PlacementStatus),
      internship_status: internshipStatus === ALL ? undefined : (internshipStatus as InternshipStatus),
      skill: debouncedSkill || undefined,
      sort_by: sortBy,
      sort_dir: sortDir,
      page,
      page_size: PAGE_SIZE,
    }),
    [debouncedSearch, department, batch, placementStatus, internshipStatus, debouncedSkill, sortBy, sortDir, page],
  );

  useEffect(() => {
    // Deliberately does not reset to a "loading" state before this async
    // call resolves -- the previous page of results stays visible while
    // a filter/search/page change is in flight, which avoids a
    // full-page flash on every keystroke or click.
    let cancelled = false;
    getInstitutionStudents(params)
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load students."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [params, reloadKey]);

  function toggleSort(field: SortBy) {
    if (sortBy === field) {
      setSortDir((d) => (d === "asc" ? "desc" : "asc"));
    } else {
      setSortBy(field);
      setSortDir("asc");
    }
    setPage(1);
  }

  const hasActiveFilters =
    !!debouncedSearch ||
    department !== ALL ||
    batch !== ALL ||
    placementStatus !== ALL ||
    internshipStatus !== ALL ||
    !!debouncedSkill;

  return (
    <div className="space-y-4">
      {state.status === "ready" ? <SummaryCards summary={state.data.summary} /> : null}

      <div className="flex flex-col gap-3 sm:flex-row sm:flex-wrap sm:items-center">
        <div className="relative w-full sm:max-w-xs">
          <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
          <Input
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            placeholder="Search students..."
            className="pl-8"
            aria-label="Search students by name or username"
          />
        </div>

        <FilterSelect
          label="Department"
          value={department}
          onChange={updateFilter(setDepartment)}
          options={
            state.status === "ready"
              ? [UNASSIGNED_DEPARTMENT_FILTER, ...state.data.filters.departments.map((d) => d.id)]
              : []
          }
          labels={
            state.status === "ready"
              ? {
                  [UNASSIGNED_DEPARTMENT_FILTER]: "Unassigned",
                  ...Object.fromEntries(state.data.filters.departments.map((d) => [d.id, d.name])),
                }
              : undefined
          }
        />
        <FilterSelect
          label="Batch"
          value={batch}
          onChange={updateFilter(setBatch)}
          options={state.status === "ready" ? state.data.filters.batches.map(String) : []}
        />
        <FilterSelect
          label="Placement"
          value={placementStatus}
          onChange={updateFilter(setPlacementStatus)}
          options={Object.keys(PLACEMENT_STATUS_LABELS)}
          labels={PLACEMENT_STATUS_LABELS}
        />
        <FilterSelect
          label="Internship"
          value={internshipStatus}
          onChange={updateFilter(setInternshipStatus)}
          options={Object.keys(INTERNSHIP_STATUS_LABELS)}
          labels={INTERNSHIP_STATUS_LABELS}
        />
        <Input
          value={skill}
          onChange={(e) => setSkill(e.target.value)}
          placeholder="Skill (e.g. Python)"
          className="w-full sm:w-40"
          aria-label="Filter by skill"
        />
      </div>

      {state.status === "loading" ? <Loading label="Loading students…" className="py-16" /> : null}

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
        state.data.total === 0 ? (
          <EmptyState
            icon={hasActiveFilters ? Search : Users}
            title={hasActiveFilters ? "No students match your filters" : "No students are linked to this institution yet"}
            description={
              hasActiveFilters
                ? "Try a different search term or clear a filter."
                : "Approve a join request to see students here."
            }
          />
        ) : (
          <>
            <StudentTable
              students={state.data.students}
              sortBy={sortBy}
              sortDir={sortDir}
              onSort={toggleSort}
              onOpen={(id) => router.push(`/institution/students/${id}`)}
            />
            <PaginationBar
              page={state.data.page}
              pageSize={state.data.page_size}
              total={state.data.total}
              onPageChange={setPage}
            />
          </>
        )
      ) : null}
    </div>
  );
}

function SummaryCards({ summary }: { summary: StudentListResponse["summary"] }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
      <StatCard label="Total Students" value={summary.total_students.toLocaleString()} icon={Users} accent="indigo" />
      <StatCard label="Placed" value={summary.placed.toLocaleString()} icon={GraduationCap} accent="emerald" />
      <StatCard label="Unplaced" value={summary.unplaced.toLocaleString()} icon={Users} accent="amber" />
      <StatCard
        label="No Applications"
        value={summary.no_applications.toLocaleString()}
        icon={Users}
        accent="violet"
      />
      <StatCard
        label="Internship Students"
        value={summary.internship_selected.toLocaleString()}
        icon={GraduationCap}
        accent="blue"
      />
    </div>
  );
}

function FilterSelect({
  label,
  value,
  onChange,
  options,
  labels,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  options: string[];
  labels?: Record<string, string>;
}) {
  return (
    <Select value={value} onValueChange={(v) => onChange(v ?? ALL)}>
      <SelectTrigger className="w-full sm:w-40" aria-label={label}>
        <SelectValue placeholder={label} />
      </SelectTrigger>
      <SelectContent>
        <SelectItem value={ALL}>{label}: All</SelectItem>
        {options.map((opt) => (
          <SelectItem key={opt} value={opt}>
            {labels?.[opt] ?? opt}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}

function SortHead({
  field,
  label,
  sortBy,
  sortDir,
  onSort,
  className,
}: {
  field: SortBy;
  label: string;
  sortBy: SortBy;
  sortDir: "asc" | "desc";
  onSort: (field: SortBy) => void;
  className?: string;
}) {
  const active = sortBy === field;
  return (
    <TableHead className={className}>
      <button
        type="button"
        onClick={() => onSort(field)}
        className="inline-flex items-center gap-1 font-medium hover:text-foreground"
      >
        {label}
        {active ? (
          sortDir === "asc" ? (
            <ArrowUp className="size-3" aria-hidden="true" />
          ) : (
            <ArrowDown className="size-3" aria-hidden="true" />
          )
        ) : null}
      </button>
    </TableHead>
  );
}

function StudentTable({
  students,
  sortBy,
  sortDir,
  onSort,
  onOpen,
}: {
  students: StudentSummary[];
  sortBy: SortBy;
  sortDir: "asc" | "desc";
  onSort: (field: SortBy) => void;
  onOpen: (id: string) => void;
}) {
  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <SortHead field="name" label="Student" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
              <SortHead field="department" label="Department" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
              <TableHead>Batch</TableHead>
              <SortHead field="cgpa" label="CGPA" sortBy={sortBy} sortDir={sortDir} onSort={onSort} className="text-right" />
              <TableHead>Skills</TableHead>
              <SortHead field="placement_status" label="Placement" sortBy={sortBy} sortDir={sortDir} onSort={onSort} />
              <TableHead>Internship</TableHead>
              <TableHead className="text-right">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {students.map((student) => (
              <TableRow
                key={student.id}
                className="cursor-pointer"
                onClick={() => onOpen(student.id)}
              >
                <TableCell>
                  <div className="flex items-center gap-2.5">
                    <Avatar className="size-8">
                      <AvatarImage src={student.avatar_url ?? undefined} alt="" />
                      <AvatarFallback className="text-xs">{initials(student.full_name)}</AvatarFallback>
                    </Avatar>
                    <div className="min-w-0">
                      <p className="truncate text-sm font-medium">
                        {student.full_name?.trim() || student.username || "Unnamed student"}
                      </p>
                      {student.username ? (
                        <p className="truncate text-xs text-muted-foreground">@{student.username}</p>
                      ) : null}
                    </div>
                  </div>
                </TableCell>
                <TableCell className="text-sm">{student.department ?? "Unspecified"}</TableCell>
                <TableCell className="text-sm tabular-nums">{student.batch ?? "—"}</TableCell>
                <TableCell className="text-right text-sm tabular-nums">
                  {student.cgpa != null ? student.cgpa.toFixed(1) : "—"}
                </TableCell>
                <TableCell>
                  <div className="flex max-w-40 flex-wrap gap-1">
                    {student.top_skills.length === 0 ? (
                      <span className="text-xs text-muted-foreground/60">—</span>
                    ) : (
                      student.top_skills.slice(0, 3).map((s) => (
                        <Badge key={s} variant="outline" className="text-[10px]">
                          {s}
                        </Badge>
                      ))
                    )}
                  </div>
                </TableCell>
                <TableCell>
                  <Badge variant={placementBadgeVariant(student.placement_status)}>
                    {PLACEMENT_STATUS_LABELS[student.placement_status]}
                  </Badge>
                </TableCell>
                <TableCell>
                  <Badge variant={internshipBadgeVariant(student.internship_status)}>
                    {INTERNSHIP_STATUS_LABELS[student.internship_status]}
                  </Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Button
                    size="sm"
                    variant="outline"
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpen(student.id);
                    }}
                  >
                    View
                  </Button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function PaginationBar({
  page,
  pageSize,
  total,
  onPageChange,
}: {
  page: number;
  pageSize: number;
  total: number;
  onPageChange: (page: number) => void;
}) {
  const totalPages = Math.max(1, Math.ceil(total / pageSize));
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(total, page * pageSize);

  return (
    <div className="flex flex-col items-center justify-between gap-2 sm:flex-row">
      <p className="text-xs text-muted-foreground">
        Showing {start}-{end} of {total} student{total === 1 ? "" : "s"}
      </p>
      <div className="flex items-center gap-2">
        <Button size="sm" variant="outline" onClick={() => onPageChange(page - 1)} disabled={page <= 1}>
          Previous
        </Button>
        <span className="text-xs text-muted-foreground">
          Page {page} of {totalPages}
        </span>
        <Button
          size="sm"
          variant="outline"
          onClick={() => onPageChange(page + 1)}
          disabled={page >= totalPages}
        >
          Next
        </Button>
      </div>
    </div>
  );
}
