"use client";

import { useEffect, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, Handshake, Plus, Search } from "lucide-react";
import { StatCard } from "@/components/dashboard/stat-card";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
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
import { getIndustryPartnerMetrics, getIndustryPartners } from "@/lib/institution/industry-partners";
import type {
  IndustryPartnerMetrics,
  IndustryPartnerRow,
} from "@/types/institution-industry";
import { RELATIONSHIP_STATUS_LABELS, RELATIONSHIP_TYPE_LABELS } from "@/types/institution-industry";
import { IndustryPartnerForm } from "@/components/institution/industry-partners/industry-partner-form";

const ALL = "__all__";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; partners: IndustryPartnerRow[]; typeOptions: string[]; statusOptions: string[]; metrics: IndustryPartnerMetrics };

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  ACTIVE: "default",
  PROSPECT: "secondary",
  INACTIVE: "outline",
};

function formatDate(value: string | null): string {
  if (!value) return "No recorded activity";
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/**
 * The Institution Industry Partners directory (Phase 8). Companies come
 * from the union of explicit relationship tags and real institution-
 * scoped recruitment/internship/drive/collaboration activity -- never a
 * fabricated "last activity" (see backend docstring).
 */
export function IndustryPartnersList() {
  const router = useRouter();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState(ALL);
  const [statusFilter, setStatusFilter] = useState(ALL);
  const [formOpen, setFormOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getIndustryPartners(), getIndustryPartnerMetrics()])
      .then(([list, metricsResp]) => {
        if (!cancelled) {
          setState({
            status: "ready",
            partners: list.partners,
            typeOptions: list.type_options,
            statusOptions: list.status_options,
            metrics: metricsResp.metrics,
          });
        }
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load industry partners."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const filtered = useMemo(() => {
    if (state.status !== "ready") return [];
    let rows = state.partners;
    if (typeFilter !== ALL) rows = rows.filter((r) => r.relationship_type === typeFilter);
    if (statusFilter !== ALL) rows = rows.filter((r) => r.relationship_status === statusFilter);
    const needle = search.trim().toLowerCase();
    if (needle) rows = rows.filter((r) => (r.company_name ?? "").toLowerCase().includes(needle));
    return rows;
  }, [state, search, typeFilter, statusFilter]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  function handleSaved() {
    setFormOpen(false);
    reload();
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Industry Partners</h1>
          <p className="text-sm text-muted-foreground">
            Companies that recruit your students, provide internships, or collaborate with your institution.
          </p>
        </div>
        <Button onClick={() => setFormOpen(true)}>
          <Plus className="size-4" /> Add Partner
        </Button>
      </div>

      {state.status === "loading" ? <Loading label="Loading industry partners…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={
            state.error.status === 401 ? "Your session has expired. Please sign in again." : state.error.message
          }
          onRetry={state.error.status !== 401 ? reload : undefined}
        />
      ) : null}

      {state.status === "ready" ? (
        <>
          <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
            <StatCard label="Total Partners" value={state.metrics.total_partners.toLocaleString()} icon={Handshake} accent="indigo" />
            <StatCard label="Active Partners" value={state.metrics.active_partners.toLocaleString()} icon={Handshake} accent="emerald" />
            <StatCard label="Recruiting" value={state.metrics.recruiting_partners.toLocaleString()} icon={Building2} accent="blue" />
            <StatCard label="Internship Partners" value={state.metrics.internship_partners.toLocaleString()} icon={Building2} accent="violet" />
          </div>

          {state.partners.length > 0 ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="relative w-full sm:max-w-xs">
                <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by company name..."
                  className="pl-8"
                  aria-label="Search companies"
                />
              </div>
              <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v ?? ALL)}>
                <SelectTrigger className="w-full sm:w-48" aria-label="Filter by relationship type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All relationship types</SelectItem>
                  {state.typeOptions.map((t) => (
                    <SelectItem key={t} value={t}>
                      {RELATIONSHIP_TYPE_LABELS[t] ?? t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v ?? ALL)}>
                <SelectTrigger className="w-full sm:w-40" aria-label="Filter by status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All statuses</SelectItem>
                  {state.statusOptions.map((s) => (
                    <SelectItem key={s} value={s}>
                      {RELATIONSHIP_STATUS_LABELS[s] ?? s}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          ) : null}

          {state.partners.length === 0 ? (
            <EmptyState
              icon={Handshake}
              title="No industry partners yet"
              description="Partners appear here once companies recruit your students, or you add one to track."
              actionLabel="Add Partner"
              onAction={() => setFormOpen(true)}
            />
          ) : filtered.length === 0 ? (
            <EmptyState icon={Search} title="No companies match your filters" />
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Company</TableHead>
                      <TableHead>Relationship</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Jobs</TableHead>
                      <TableHead className="text-right">Internships</TableHead>
                      <TableHead className="text-right">Drives</TableHead>
                      <TableHead className="text-right">Students Selected</TableHead>
                      <TableHead>Last Activity</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((p) => (
                      <TableRow
                        key={p.id}
                        className="cursor-pointer"
                        onClick={() => router.push(`/institution/industry-partners/${p.id}`)}
                      >
                        <TableCell className="font-medium hover:underline">
                          {p.company_name ?? "Unknown company"}
                          {p.industry_sector ? (
                            <span className="ml-1.5 text-xs font-normal text-muted-foreground">
                              {p.industry_sector}
                            </span>
                          ) : null}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {p.relationship_type ? RELATIONSHIP_TYPE_LABELS[p.relationship_type] ?? p.relationship_type : "—"}
                        </TableCell>
                        <TableCell>
                          {p.relationship_status ? (
                            <Badge variant={STATUS_VARIANT[p.relationship_status] ?? "outline"}>
                              {RELATIONSHIP_STATUS_LABELS[p.relationship_status] ?? p.relationship_status}
                            </Badge>
                          ) : (
                            <span className="text-xs text-muted-foreground">Not tracked</span>
                          )}
                        </TableCell>
                        <TableCell className="text-right tabular-nums">{p.jobs_opportunities}</TableCell>
                        <TableCell className="text-right tabular-nums">{p.internship_opportunities}</TableCell>
                        <TableCell className="text-right tabular-nums">{p.placement_drives_count}</TableCell>
                        <TableCell className="text-right tabular-nums">{p.students_selected}</TableCell>
                        <TableCell className="text-muted-foreground">{formatDate(p.last_activity_at)}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      ) : null}

      <IndustryPartnerForm open={formOpen} onOpenChange={setFormOpen} onSaved={handleSaved} />
    </div>
  );
}
