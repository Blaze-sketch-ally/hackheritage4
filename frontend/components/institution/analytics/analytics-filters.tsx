"use client";

import { Filter } from "lucide-react";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import type { AnalyticsFilterOptions } from "@/types/institution-analytics-report";

const ALL_VALUE = "__all__";
const UNASSIGNED_VALUE = "unassigned";

export interface AnalyticsFilterState {
  departmentId: string | null;
  batch: number | null;
}

/**
 * Department + batch selectors for the Analytics workspace. Options come
 * straight from the API response's own `filter_options` (the same
 * department list / batch list the Student Directory already exposes) --
 * never a second derivation. See analytics_service.py's own docstring for
 * exactly which sections these narrow (`filter_scope_note`, always
 * rendered by AnalyticsView).
 */
export function AnalyticsFilters({
  options,
  value,
  onChange,
}: {
  options: AnalyticsFilterOptions;
  value: AnalyticsFilterState;
  onChange: (next: AnalyticsFilterState) => void;
}) {
  const hasActiveFilter = value.departmentId != null || value.batch != null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="flex items-center gap-1 text-xs font-medium text-muted-foreground">
        <Filter className="size-3.5" aria-hidden="true" />
        Filters
      </span>

      <Select
        value={value.departmentId ?? ALL_VALUE}
        onValueChange={(v) => onChange({ ...value, departmentId: v === ALL_VALUE ? null : v })}
      >
        <SelectTrigger className="w-full sm:w-48" aria-label="Filter by department">
          <SelectValue placeholder="All departments" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_VALUE}>All departments</SelectItem>
          <SelectItem value={UNASSIGNED_VALUE}>Unassigned</SelectItem>
          {options.departments.map((d) => (
            <SelectItem key={d.id} value={d.id}>
              {d.name}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      <Select
        value={value.batch != null ? String(value.batch) : ALL_VALUE}
        onValueChange={(v) => onChange({ ...value, batch: v === ALL_VALUE ? null : Number(v) })}
      >
        <SelectTrigger className="w-full sm:w-36" aria-label="Filter by batch">
          <SelectValue placeholder="All batches" />
        </SelectTrigger>
        <SelectContent>
          <SelectItem value={ALL_VALUE}>All batches</SelectItem>
          {options.batches.map((b) => (
            <SelectItem key={b} value={String(b)}>
              Batch {b}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>

      {hasActiveFilter ? (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onChange({ departmentId: null, batch: null })}
        >
          Clear
        </Button>
      ) : null}
    </div>
  );
}
