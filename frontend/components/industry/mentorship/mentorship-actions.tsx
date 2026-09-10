"use client";

import { Button } from "@/components/ui/button";
import type { MentorshipStatus } from "@/types/industry-mentorship";

/** The lifecycle buttons appropriate to a mentorship opportunity's
 * current status. Shared by the list cards and the detail view. The
 * parent owns the confirmation dialogs and the actual API calls. */
export function MentorshipActions({
  status,
  pending,
  onPublish,
  onClose,
  onArchive,
  size = "sm",
}: {
  status: MentorshipStatus;
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
