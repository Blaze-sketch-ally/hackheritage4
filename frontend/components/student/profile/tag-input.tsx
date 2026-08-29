"use client";

import { useId, useState } from "react";
import { X } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Label } from "@/components/ui/label";

interface TagInputProps {
  label: string;
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
  disabled?: boolean;
}

/** Comma/Enter-delimited tag input for array fields (skills, roles, locations). */
export function TagInput({ label, values, onChange, placeholder, disabled }: TagInputProps) {
  const id = useId();
  const [draft, setDraft] = useState("");

  function commit() {
    const trimmed = draft.trim();
    setDraft("");
    if (!trimmed) return;
    if (values.some((v) => v.toLowerCase() === trimmed.toLowerCase())) return;
    onChange([...values, trimmed]);
  }

  function handleKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      commit();
    } else if (e.key === "Backspace" && !draft && values.length > 0) {
      onChange(values.slice(0, -1));
    }
  }

  return (
    <div className="space-y-1.5">
      <Label htmlFor={id}>{label}</Label>
      <div
        className="flex flex-wrap items-center gap-1.5 rounded-lg border border-input px-2 py-1.5 has-focus:border-ring has-focus:ring-3 has-focus:ring-ring/50"
      >
        {values.map((value, index) => (
          <Badge key={value} variant="secondary" className="gap-1">
            {value}
            {disabled ? null : (
              <button
                type="button"
                onClick={() => onChange(values.filter((_, i) => i !== index))}
                aria-label={`Remove ${value}`}
                className="rounded-full outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <X className="size-3" />
              </button>
            )}
          </Badge>
        ))}
        <input
          id={id}
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          onBlur={commit}
          placeholder={values.length === 0 ? placeholder : undefined}
          disabled={disabled}
          className="min-w-24 flex-1 bg-transparent py-0.5 text-sm outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
        />
      </div>
      <p className="text-xs text-muted-foreground">Press Enter or comma to add.</p>
    </div>
  );
}
