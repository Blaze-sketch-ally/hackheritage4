"use client";

import { Button } from "@/components/ui/button";
import {
  APPLICATION_TRANSITIONS,
  TRANSITION_LABELS,
  type Application,
  type IndustrySettableStatus,
} from "@/types/application";

/** Buttons for the valid next statuses of an application, given its
 * current status. The parent owns the confirmation dialog and the API
 * call. Shows nothing for terminal statuses (SELECTED / REJECTED /
 * WITHDRAWN). */
export function ApplicationStatusActions({
  status,
  pending,
  onPick,
  size = "sm",
}: {
  status: Application["status"];
  pending: boolean;
  onPick: (target: IndustrySettableStatus) => void;
  size?: "sm" | "default";
}) {
  const targets = APPLICATION_TRANSITIONS[status];
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
          {TRANSITION_LABELS[target]}
        </Button>
      ))}
    </>
  );
}
