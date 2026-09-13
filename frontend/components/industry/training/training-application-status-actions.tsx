"use client";

import { Button } from "@/components/ui/button";
import {
  TRAINING_APPLICATION_TRANSITIONS,
  TRAINING_TRANSITION_LABELS,
  type IndustrySettableTrainingStatus,
  type TrainingApplicationStatus,
} from "@/types/training-application";

export function TrainingApplicationStatusActions({
  status,
  pending,
  onPick,
  size = "sm",
}: {
  status: TrainingApplicationStatus;
  pending: boolean;
  onPick: (target: IndustrySettableTrainingStatus) => void;
  size?: "sm" | "default";
}) {
  const targets = TRAINING_APPLICATION_TRANSITIONS[status];
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
          {TRAINING_TRANSITION_LABELS[target]}
        </Button>
      ))}
    </>
  );
}
