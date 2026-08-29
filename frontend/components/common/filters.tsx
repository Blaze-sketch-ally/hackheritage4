"use client";

import { useMemo } from "react";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";

export interface FilterOption {
  value: string;
  label: string;
}

export function Filters({
  value,
  onChange,
  options,
  "aria-label": ariaLabel = "Filter",
}: {
  value: string;
  onChange: (value: string) => void;
  options: FilterOption[];
  "aria-label"?: string;
}) {
  // Lets Select.Value resolve the trigger's label from `value` without the
  // popup having to be opened/mounted first.
  const items = useMemo(() => Object.fromEntries(options.map((o) => [o.value, o.label])), [options]);

  return (
    <Select value={value} onValueChange={(next) => onChange(next as string)} items={items}>
      <SelectTrigger aria-label={ariaLabel} className="w-full sm:w-52">
        <SelectValue />
      </SelectTrigger>
      <SelectContent>
        {options.map((option) => (
          <SelectItem key={option.value} value={option.value}>
            {option.label}
          </SelectItem>
        ))}
      </SelectContent>
    </Select>
  );
}
