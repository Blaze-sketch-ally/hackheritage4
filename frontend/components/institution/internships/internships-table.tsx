"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { Briefcase, Search, X } from "lucide-react";
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
import type { InstitutionInternshipRow } from "@/types/institution-internship";

const ALL = "__all__";

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline" | "destructive"> = {
  PUBLISHED: "default",
  CLOSED: "secondary",
  ARCHIVED: "outline",
  DRAFT: "outline",
};

function formatStipend(amount: number | null, currency: string | null): string {
  if (amount == null) return "Unpaid / not specified";
  return `${currency ?? ""} ${amount.toLocaleString()}`.trim();
}

/**
 * This institution's CURATED / SELECTED internship list -- the module's
 * default view. Every row here is one this institution explicitly added
 * via "Add to Institution" (see AvailableInternshipsTable); removing one
 * soft-deactivates its association without touching the canonical
 * internship.
 */
export function InternshipsTable({
  internships,
  statusOptions,
  modeOptions,
  onRemove,
  removingId,
}: {
  internships: InstitutionInternshipRow[];
  statusOptions: string[];
  modeOptions: string[];
  onRemove?: (internshipId: string) => void;
  removingId?: string | null;
}) {
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState(ALL);
  const [modeFilter, setModeFilter] = useState(ALL);

  const filtered = useMemo(() => {
    let rows = internships;
    if (statusFilter !== ALL) rows = rows.filter((r) => r.status === statusFilter);
    if (modeFilter !== ALL) rows = rows.filter((r) => r.work_mode === modeFilter);
    const needle = search.trim().toLowerCase();
    if (needle) {
      rows = rows.filter(
        (r) => r.title.toLowerCase().includes(needle) || (r.company_name ?? "").toLowerCase().includes(needle),
      );
    }
    return rows;
  }, [internships, search, statusFilter, modeFilter]);

  return (
    <div className="space-y-3">
      {internships.length > 0 ? (
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
          <div className="relative w-full sm:max-w-xs">
            <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
            <Input
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="Search by title or company..."
              className="pl-8"
              aria-label="Search internships"
            />
          </div>
          <Select value={statusFilter} onValueChange={(v) => setStatusFilter(v ?? ALL)}>
            <SelectTrigger className="w-full sm:w-40" aria-label="Filter by status">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {statusOptions.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
          <Select value={modeFilter} onValueChange={(v) => setModeFilter(v ?? ALL)}>
            <SelectTrigger className="w-full sm:w-40" aria-label="Filter by mode">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All modes</SelectItem>
              {modeOptions.map((m) => (
                <SelectItem key={m} value={m}>
                  {m}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {internships.length === 0 ? (
        <EmptyState
          icon={Briefcase}
          title="No internships selected yet"
          description="Browse available internships and add the ones you want to curate for your institution."
        />
      ) : filtered.length === 0 ? (
        <EmptyState icon={Search} title="No internships match your filters" />
      ) : (
        <Card>
          <CardContent className="p-0">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Internship</TableHead>
                  <TableHead>Company</TableHead>
                  <TableHead>Mode</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead>Stipend</TableHead>
                  <TableHead>Deadline</TableHead>
                  <TableHead className="text-right">Applicants</TableHead>
                  <TableHead className="text-right">Selected</TableHead>
                  <TableHead>Status</TableHead>
                  {onRemove ? <TableHead className="text-right">Actions</TableHead> : null}
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">
                      <Link href={`/institution/internships/${r.id}`} className="hover:underline">
                        {r.title}
                      </Link>
                    </TableCell>
                    <TableCell className="text-muted-foreground">{r.company_name ?? "—"}</TableCell>
                    <TableCell>{r.work_mode ?? "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.duration_months != null ? `${r.duration_months} mo` : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatStipend(r.stipend_amount, r.stipend_currency)}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{r.application_deadline ?? "—"}</TableCell>
                    <TableCell className="text-right tabular-nums">{r.applicants_from_institution}</TableCell>
                    <TableCell className="text-right tabular-nums">{r.selected_from_institution}</TableCell>
                    <TableCell>
                      <Badge variant={STATUS_VARIANT[r.status] ?? "outline"}>{r.status}</Badge>
                    </TableCell>
                    {onRemove ? (
                      <TableCell className="text-right">
                        <Button
                          variant="ghost"
                          size="sm"
                          disabled={removingId === r.id}
                          onClick={() => onRemove(r.id)}
                          aria-label={`Remove ${r.title} from your institution`}
                        >
                          <X className="size-4" /> Remove
                        </Button>
                      </TableCell>
                    ) : null}
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      )}
    </div>
  );
}
