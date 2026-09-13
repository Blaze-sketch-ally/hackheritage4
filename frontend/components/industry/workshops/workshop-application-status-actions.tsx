"use client";

import { Button } from "@/components/ui/button";
import {
  WORKSHOP_APPLICATION_TRANSITIONS,
  WORKSHOP_TRANSITION_LABELS,
  type IndustrySettableWorkshopStatus,
  type WorkshopApplicationStatus,
} from "@/types/workshop-application";

export function WorkshopApplicationStatusActions({
  status,
  pending,
  onPick,
  size = "sm",
}: {
  status: WorkshopApplicationStatus;
  pending: boolean;
  onPick: (target: IndustrySettableWorkshopStatus) => void;
  size?: "sm" | "default";
}) {
  const targets = WORKSHOP_APPLICATION_TRANSITIONS[status];
  if (targets.length === 0) return null;

  return (
    <>
      {targets.map((target) => (
        <Button
          key={target}
          size={size}
          variant={target === "REJECTED" ? "ghost" : target === "ACCEPTED" ? "default" : "outline"}
          onClick={() => onPick(target)}
          disabled={pending}
        >
          {WORKSHOP_TRANSITION_LABELS[target]}
        </Button>
      ))}
    </>
  );
}
