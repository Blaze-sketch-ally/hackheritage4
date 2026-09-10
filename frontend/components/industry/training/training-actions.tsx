"use client";

import { Button } from "@/components/ui/button";
import type { TrainingStatus } from "@/types/industry-training";

/** The lifecycle buttons appropriate to a training record's current
 * status. Shared by the list cards and the detail view. The parent owns
 * the confirmation dialogs and the actual API calls. */
export function TrainingActions({
  status,
  pending,
  onPublish,
  onClose,
  onArchive,
  size = "sm",
}: {
  status: TrainingStatus;
  pending: boolean;
  onPublish: () => void;
  onClose: () => void;
  onArchive: () => void;
  size?: "sm" | "default";
}) {
  return (
    <>
      {status === "DRAFT" || status === "CLOSED" ? (
        <Button size={size} onClick={onPublish} disabled={pending}>
          Publish
        </Button>
      ) : null}
      {status === "PUBLISHED" ? (
        <Button size={size} variant="outline" onClick={onClose} disabled={pending}>
          Close
        </Button>
      ) : null}
      {status !== "ARCHIVED" ? (
        <Button size={size} variant="ghost" onClick={onArchive} disabled={pending}>
          Archive
        </Button>
      ) : null}
    </>
  );
}
