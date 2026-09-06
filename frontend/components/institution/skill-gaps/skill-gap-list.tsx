"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { ClipboardList, Search } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
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
import { getSkillGapApplications } from "@/lib/institution/skill-gaps";
import {
  APPLICATION_STATUS_LABELS,
  OPPORTUNITY_TYPE_LABELS,
  type ApplicationStatus,
  type MatchRecommendation,
  type OpportunityType,
} from "@/types/application";
import type { SkillGapApplicationSummary } from "@/types/institution-skill-gap";

const ALL = "all";

type ListState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; applications: SkillGapApplicationSummary[] };

const RECOMMENDATION_CLASS: Record<MatchRecommendation, string> = {
  STRONG: "bg-green-600/10 text-green-700 dark:text-green-400",
  GOOD: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  PARTIAL: "bg-amber-500/10 text-amber-700 dark:text-amber-400",
  LOW: "bg-muted text-muted-foreground",
};

/**
 * Institution Skill Gap Analysis: for each application by one of this
 * institution's own linked students, how their recorded skills compare to
 * what the internship/job actually requires
 * (GET /api/v1/institution/skill-gaps). This is deliberately
 * application-specific, not an institution-wide skill dashboard -- see
 * institution_skill_gap_service.py's own docstring.
 */
export function SkillGapList() {
  const router = useRouter();
  const [search, setSearch] = useState("");
  const [debouncedSearch, setDebouncedSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState<string>(ALL);
  const [statusFilter, setStatusFilter] = useState<string>(ALL);
  const [state, setState] = useState<ListState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    const timer = setTimeout(() => setDebouncedSearch(search), 300);
    return () => clearTimeout(timer);
  }, [search]);

  useEffect(() => {
    let cancelled = false;
    getSkillGapApplications({
      search: debouncedSearch || undefined,
      opportunity_type: typeFilter === ALL ? undefined : (typeFilter as OpportunityType),
      status: statusFilter === ALL ? undefined : (statusFilter as ApplicationStatus),
    })
      .then(({ applications }) => {
        if (!cancelled) setState({ status: "ready", applications });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load skill gap data."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [debouncedSearch, typeFilter, statusFilter, reloadKey]);

  const hasAnyApplications = state.status === "ready" && state.applications.length > 0;
  const hasActiveFilters = !!debouncedSearch || typeFilter !== ALL || statusFilter !== ALL;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Skill Gap Analysis</h1>
        <p className="text-sm text-muted-foreground">
          Review skill gaps for students applying to jobs and internships.
        </p>
      </div>

      {hasAnyApplications || hasActiveFilters ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by student, opportunity, or company…"
              className="pl-8"
              aria-label="Search applications"
            />
          </div>
          <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v ?? ALL)}>
            <SelectTrigger className="w-full sm:w-40" aria-label="Opportunity type">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All types</SelectItem>
              {Object.entries(OPPORTUNITY_TYPE_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v ?? ALL)}>
            <SelectTrigger className="w-full sm:w-44" aria-label="Application status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {Object.entries(APPLICATION_STATUS_LABELS).map(([value, label]) => (
                <SelectItem key={value} value={value}>
                  {label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {state.status === "loading" ? <Loading label="Loading skill gap data…" className="py-16" /> : null}

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
        state.applications.length === 0 ? (
          hasActiveFilters ? (
            <EmptyState
              icon={Search}
              title="No applications match your filters"
              description="Try a different search term or clear the filters."
            />
          ) : (
            <EmptyState
              icon={ClipboardList}
              title="No student applications available for skill-gap analysis."
              description="Once your students apply to jobs or internships, their skill gaps will appear here."
            />
          )
        ) : (
          <ApplicationTable
            applications={state.applications}
            onOpen={(id) => router.push(`/institution/skill-gaps/${id}`)}
          />
        )
      ) : null}
    </div>
  );
}

function ApplicationTable({
  applications,
  onOpen,
}: {
  applications: SkillGapApplicationSummary[];
  onOpen: (applicationId: string) => void;
}) {
  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>Student</TableHead>
              <TableHead>Opportunity</TableHead>
              <TableHead>Type</TableHead>
              <TableHead>Status</TableHead>
              <TableHead className="text-right">Match</TableHead>
              <TableHead className="text-right">Matched</TableHead>
              <TableHead className="text-right">Missing</TableHead>
              <TableHead className="sr-only">Actions</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {applications.map((app) => (
              <TableRow key={app.application_id} className="cursor-pointer" onClick={() => onOpen(app.application_id)}>
                <TableCell>
                  <p className="font-medium">{app.full_name ?? "Unknown student"}</p>
                  <p className="text-xs text-muted-foreground">
                    {app.username ? `@${app.username}` : app.company_name ?? "—"}
                  </p>
                </TableCell>
                <TableCell>
                  <p className="text-sm">{app.opportunity_title ?? "Untitled posting"}</p>
                  <p className="text-xs text-muted-foreground">{app.company_name ?? "—"}</p>
                </TableCell>
                <TableCell className="text-sm">{OPPORTUNITY_TYPE_LABELS[app.opportunity_type]}</TableCell>
                <TableCell>
                  <Badge variant="outline">{APPLICATION_STATUS_LABELS[app.status]}</Badge>
                </TableCell>
                <TableCell className="text-right">
                  <Badge variant="ghost" className={RECOMMENDATION_CLASS[app.recommendation]}>
                    {app.score}%
                  </Badge>
                </TableCell>
                <TableCell className="text-right tabular-nums">{app.matched_count}</TableCell>
                <TableCell className="text-right tabular-nums">{app.missing_count}</TableCell>
                <TableCell className="text-right">
                  <button
                    type="button"
                    className="text-sm font-medium text-indigo-600 hover:underline dark:text-indigo-400"
                    onClick={(e) => {
                      e.stopPropagation();
                      onOpen(app.application_id);
                    }}
                  >
                    View Skill Gap
                  </button>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}
