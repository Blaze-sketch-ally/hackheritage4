"use client";

import { Button } from "@/components/ui/button";
import {
  PROJECT_APPLICATION_TRANSITIONS,
  PROJECT_TRANSITION_LABELS,
  type IndustrySettableProjectStatus,
  type ProjectApplicationStatus,
} from "@/types/project-application";

export function ProjectApplicationStatusActions({
  status,
  pending,
  onPick,
  size = "sm",
}: {
  status: ProjectApplicationStatus;
  pending: boolean;
  onPick: (target: IndustrySettableProjectStatus) => void;
  size?: "sm" | "default";
}) {
  const targets = PROJECT_APPLICATION_TRANSITIONS[status];
  if (targets.length === 0) return null;

  return (
    <>
      {targets.map((target) => (
        <Button
          key={target}
          size={size}
          variant={target === "REJECTED" ? "ghost" : target === "SELECTED" ? "default" : "outline"}
          onClick={() => onPick(target)}
          disabled={pending}
        >
          {PROJECT_TRANSITION_LABELS[target]}
        </Button>
      ))}
    </>
  );
}
