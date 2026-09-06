"use client";

import { useMemo, useState } from "react";
import { Plus, Search, Sparkles } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
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
import type { AvailableInternshipRow } from "@/types/institution-internship";

const ALL = "__all__";

function formatStipend(amount: number | null, currency: string | null): string {
  if (amount == null) return "Unpaid / not specified";
  return `${currency ?? ""} ${amount.toLocaleString()}`.trim();
}

/**
 * Internships posted by Industry that this institution has NOT yet
 * curated -- the browse source for "Add to Institution". Selecting one
 * moves it into the curated tab; it never edits the canonical internship.
 */
export function AvailableInternshipsTable({
  internships,
  modeOptions,
  onAdd,
  addingId,
}: {
  internships: AvailableInternshipRow[];
  modeOptions: string[];
  onAdd: (internshipId: string) => void;
  addingId?: string | null;
}) {
  const [search, setSearch] = useState("");
  const [modeFilter, setModeFilter] = useState(ALL);

  const filtered = useMemo(() => {
    let rows = internships;
    if (modeFilter !== ALL) rows = rows.filter((r) => r.work_mode === modeFilter);
    const needle = search.trim().toLowerCase();
    if (needle) {
      rows = rows.filter(
        (r) => r.title.toLowerCase().includes(needle) || (r.company_name ?? "").toLowerCase().includes(needle),
      );
    }
    return rows;
  }, [internships, search, modeFilter]);

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
              aria-label="Search available internships"
            />
          </div>
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
          icon={Sparkles}
          title="No available internships right now"
          description="Every currently published internship has already been added to your institution."
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
                  <TableHead>Stipend</TableHead>
                  <TableHead className="text-right">Duration</TableHead>
                  <TableHead>Deadline</TableHead>
                  <TableHead className="text-right">Action</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {filtered.map((r) => (
                  <TableRow key={r.id}>
                    <TableCell className="font-medium">{r.title}</TableCell>
                    <TableCell className="text-muted-foreground">{r.company_name ?? "—"}</TableCell>
                    <TableCell>{r.work_mode ?? "—"}</TableCell>
                    <TableCell className="text-muted-foreground">
                      {formatStipend(r.stipend_amount, r.stipend_currency)}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">
                      {r.duration_months != null ? `${r.duration_months} mo` : "—"}
                    </TableCell>
                    <TableCell className="text-muted-foreground">{r.application_deadline ?? "—"}</TableCell>
                    <TableCell className="text-right">
                      <Button
                        variant="outline"
                        size="sm"
                        disabled={addingId === r.id}
                        onClick={() => onAdd(r.id)}
                      >
                        <Plus className="size-4" /> Add to Institution
                      </Button>
                    </TableCell>
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
