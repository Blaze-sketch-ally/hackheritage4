"use client";

import { Button } from "@/components/ui/button";
import type { CollaborationStatus } from "@/types/industry-collaboration";

/** The lifecycle buttons appropriate to a collaboration's current status,
 * from the Industry (initiator) side. Shared by the list cards and the
 * detail view. The parent owns the confirmation dialogs and the actual
 * API calls. Unlike the posting modules, there is no publish/close/
 * archive here — send/activate/complete/cancel instead. */
export function CollaborationActions({
  status,
  pending,
  onSend,
  onActivate,
  onComplete,
  onCancel,
  size = "sm",
}: {
  status: CollaborationStatus;
  pending: boolean;
  onSend: () => void;
  onActivate: () => void;
  onComplete: () => void;
  onCancel: () => void;
  size?: "sm" | "default";
}) {
  const cancellable = status === "DRAFT" || status === "SENT" || status === "ACCEPTED" || status === "ACTIVE";

  return (
    <>
      {status === "DRAFT" ? (
        <Button size={size} onClick={onSend} disabled={pending}>
          Send
        </Button>
      ) : null}
      {status === "ACCEPTED" ? (
        <Button size={size} onClick={onActivate} disabled={pending}>
          Activate
        </Button>
      ) : null}
      {status === "ACTIVE" ? (
        <Button size={size} onClick={onComplete} disabled={pending}>
          Complete
        </Button>
      ) : null}
      {cancellable ? (
        <Button size={size} variant="ghost" onClick={onCancel} disabled={pending}>
          Cancel
        </Button>
      ) : null}
    </>
  );
}
