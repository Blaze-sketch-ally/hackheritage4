"use client";

import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Filters, type FilterOption } from "@/components/common/filters";
import { SearchBar } from "@/components/common/search-bar";
import {
  LEARNING_DIFFICULTIES,
  LEARNING_RESOURCE_TYPES,
  resourceTypeLabel,
} from "@/types/student-learning";

export interface LearningFilterState {
  /** Client-side title/provider match (the backend has no search param). */
  search: string;
  /** Server-side filter -> GET /resources?difficulty=... ; "all" = omit. */
  difficulty: string;
  /** Server-side filter -> GET /resources?resource_type=... ; "all" = omit. */
  resourceType: string;
}

export const EMPTY_LEARNING_FILTERS: LearningFilterState = {
  search: "",
  difficulty: "all",
  resourceType: "all",
};

const DIFFICULTY_OPTIONS: FilterOption[] = [
  { value: "all", label: "All levels" },
  ...LEARNING_DIFFICULTIES.map((d) => ({ value: d, label: d })),
];

const TYPE_OPTIONS: FilterOption[] = [
  { value: "all", label: "All types" },
  ...LEARNING_RESOURCE_TYPES.map((t) => ({ value: t, label: resourceTypeLabel(t) })),
];

export function learningFiltersActive(filters: LearningFilterState): boolean {
  return (
    filters.search.trim() !== "" ||
    filters.difficulty !== "all" ||
    filters.resourceType !== "all"
  );
}

export function LearningResourceFilters({
  filters,
  onChange,
}: {
  filters: LearningFilterState;
  onChange: (next: LearningFilterState) => void;
}) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:flex-wrap sm:items-center">
      <SearchBar
        value={filters.search}
        onChange={(search) => onChange({ ...filters, search })}
        placeholder="Search by title or provider..."
        aria-label="Search learning resources"
      />
      <Filters
        value={filters.difficulty}
        onChange={(difficulty) => onChange({ ...filters, difficulty })}
        options={DIFFICULTY_OPTIONS}
        aria-label="Filter by level"
      />
      <Filters
        value={filters.resourceType}
        onChange={(resourceType) => onChange({ ...filters, resourceType })}
        options={TYPE_OPTIONS}
        aria-label="Filter by type"
      />
      {learningFiltersActive(filters) && (
        <Button
          variant="ghost"
          size="sm"
          onClick={() => onChange({ ...EMPTY_LEARNING_FILTERS })}
        >
          <X className="size-3.5" /> Clear
        </Button>
      )}
    </div>
  );
}
