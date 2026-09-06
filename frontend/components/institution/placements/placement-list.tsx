"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Briefcase, GraduationCap, Plus, Search, Users } from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
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
import { getPlacementDrives, getPlacementOverview } from "@/lib/institution/placements";
import {
  DRIVE_STATUS_LABELS,
  type DriveStatus,
  type PlacementDriveSummary,
  type PlacementOverviewResponse,
} from "@/types/institution-placement";
import { PlacementDriveForm } from "@/components/institution/placements/placement-drive-form";

const ALL = "all";

type ListState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; drives: PlacementDriveSummary[] };

type OverviewState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; overview: PlacementOverviewResponse };

function statusBadgeVariant(status: DriveStatus): "default" | "secondary" | "outline" | "destructive" {
  if (status === "OPEN" || status === "IN_PROGRESS") return "default";
  if (status === "COMPLETED") return "secondary";
  if (status === "CANCELLED") return "destructive";
  return "outline";
}

/**
 * The Institution Placements page: coordinates existing company jobs via
 * placement drives (GET/POST /api/v1/institution/placements...). Never a
 * parallel jobs/applications system -- every drive references an
 * existing `jobs` row and every applicant/selected count comes straight
 * from the existing `applications` table (status = 'SELECTED' = placed).
 */
export function PlacementList() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<string>(ALL);
  const [state, setState] = useState<ListState>({ status: "loading" });
  const [overview, setOverview] = useState<OverviewState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let cancelled = false;
    getPlacementDrives({
      search: debouncedSearch || undefined,
      status: statusFilter === ALL ? undefined : (statusFilter as DriveStatus),
    })
      .then(({ drives }) => {
        if (!cancelled) setState({ status: "ready", drives });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load placement drives."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedSearch, statusFilter, reloadKey]);

  useEffect(() => {
    let cancelled = false;
    getPlacementOverview()
      .then((data) => {
        if (!cancelled) setOverview({ status: "ready", overview: data });
      })
      .catch(() => {
        if (!cancelled) setOverview({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const hasAnyDrives = state.status === "ready" && state.drives.length > 0;
  const hasActiveFilters = !!debouncedSearch || statusFilter !== ALL;

  function handleCreated() {
    setFormOpen(false);
    setState({ status: "loading" });
    setOverview({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Placement Drives</h1>
          <p className="text-sm text-muted-foreground">
            Coordinate your students&apos; participation in company job postings.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="size-4" /> New Drive
        </Button>
      </div>

      {overview.status === "ready" ? <OverviewCards overview={overview.overview} /> : null}

      {hasAnyDrives || hasActiveFilters ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by title, job or company..."
              className="pl-8"
              aria-label="Search placement drives"
            />
          </div>
          <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v ?? ALL)}>
            <SelectTrigger className="w-full sm:w-44" aria-label="Status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {Object.entries(DRIVE_STATUS_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {state.status === "loading" ? <Loading label="Loading placement drives…" className="py-16" /> : null}

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
        state.drives.length === 0 ? (
          hasActiveFilters ? (
            <EmptyState
              icon={Search}
              title="No placement drives match your filters"
              description="Try a different search term or clear the status filter."
            />
          ) : (
            <EmptyState
              icon={Briefcase}
              title="No placement drives yet"
              description="Create a drive to coordinate your students' participation in a published company job."
              actionLabel="New Drive"
              onAction={() => setFormOpen(true)}
            />
          )
        ) : (
          <DriveTable drives={state.drives} onOpen={(id) => router.push(`/institution/placements/${id}`)} />
        )
      ) : null}

      <PlacementDriveForm open={formOpen} onOpenChange={setFormOpen} onSaved={handleCreated} />
    </div>
  );
}

function OverviewCards({ overview }: { overview: PlacementOverviewResponse }) {
  return (
    <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
      <StatCard label="Active Drives" value={overview.active_drives.toLocaleString()} icon={Briefcase} accent="indigo" />
      <StatCard
        label="Participating Students"
        value={overview.participating_students.toLocaleString()}
        icon={Users}
        accent="blue"
      />
      <StatCard
        label="Placed Students"
        value={overview.placed_students.toLocaleString()}
        icon={GraduationCap}
        accent="emerald"
      />
      <StatCard
        label="Placement Rate"
        value={overview.placement_rate != null ? `${overview.placement_rate}%` : "—"}
        helperText={overview.participating_students === 0 ? "no participants yet" : "across drive-linked jobs"}
        icon={GraduationCap}
        accent="violet"
      />
    </div>
  );
}

function DriveTable({ drives, onOpen }: { drives: PlacementDriveSummary[]; onOpen: (id: string) => void }) {
  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Drive</TableHead>
              <TableHead>Company</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Eligible</TableHead>
              <TableHead className="text-right">Applied</TableHead>
              <TableHead className="text-right">Selected</TableHead>
              <TableHead>Deadline</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {drives.map((drive) => (
              <TableRow key={drive.id} className="cursor-pointer" onClick={() => onOpen(drive.id)}>
                <TableCell>
                  <p className="font-medium">{drive.title}</p>
                  <p className="text-xs text-muted-foreground">{drive.job_title ?? "Untitled job"}</p>
                </TableCell>
                <TableCell className="text-sm">{drive.company_name ?? "—"}</TableCell>
                <TableCell>
                  <Badge variant={statusBadgeVariant(drive.status)}>{DRIVE_STATUS_LABELS[drive.status]}</Badge>
                </TableCell>
                <TableCell className="text-right tabular-nums">{drive.eligible_count}</TableCell>
                <TableCell className="text-right tabular-nums">{drive.applied_count}</TableCell>
                <TableCell className="text-right tabular-nums">{drive.selected_count}</TableCell>
                <TableCell className="text-sm text-muted-foreground">
                  {drive.application_deadline ?? "—"}
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
