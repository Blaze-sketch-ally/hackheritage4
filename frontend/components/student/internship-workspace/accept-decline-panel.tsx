"use client";

import { useState } from "react";
import { AlertCircle, Check, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";

type Choice = "accept" | "decline";
type Phase = { kind: "idle" } | { kind: "confirm"; choice: Choice } | { kind: "working" };

/** PENDING_ACCEPTANCE only. Two-step (click -> confirm) so the decision
 * is deliberate, and the buttons are disabled while a request is in
 * flight so it can't be double-submitted. On success the parent swaps the
 * whole view via `onAccepted` / `onDeclined`. */
export function AcceptDeclinePanel({
  onAccept,
  onDecline,
  onAccepted,
  onDeclined,
}: {
  onAccept: () => Promise<void>;
  onDecline: (reason?: string) => Promise<void>;
  onAccepted: () => void;
  onDeclined: () => void;
}) {
  const [phase, setPhase] = useState<Phase>({ kind: "idle" });
  const [error, setError] = useState<string | null>(null);

  async function run(choice: Choice) {
    setPhase({ kind: "working" });
    setError(null);
    try {
      if (choice === "accept") {
        await onAccept();
        onAccepted();
      } else {
        await onDecline();
        onDeclined();
      }
    } catch (err) {
      setPhase({ kind: "idle" });
      setError(
        err instanceof Error
          ? err.message
          : `Could not ${choice} this internship. Please try again.`,
      );
    }
  }

  const working = phase.kind === "working";

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 py-5">
        <div>
          <p className="font-medium">Accept this internship?</p>
          <p className="text-sm text-muted-foreground">
            Accepting opens the training workspace so you can choose your skills and
            start. Declining lets the industry know you won&apos;t be taking it.
          </p>
        </div>

        {error && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="size-3.5" /> {error}
          </p>
        )}

        {phase.kind === "confirm" ? (
          <div className="flex flex-wrap items-center gap-2">
            <span className="text-sm">
              {phase.choice === "accept"
                ? "Accept this internship?"
                : "Decline this internship?"}
            </span>
            <Button
              size="sm"
              variant={phase.choice === "accept" ? "default" : "destructive"}
              onClick={() => run(phase.choice)}
            >
              Yes, {phase.choice}
            </Button>
            <Button size="sm" variant="ghost" onClick={() => setPhase({ kind: "idle" })}>
              Cancel
            </Button>
          </div>
        ) : (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              onClick={() => setPhase({ kind: "confirm", choice: "accept" })}
              disabled={working}
            >
              {working && <Loader2 className="size-3.5 animate-spin" />}
              {!working && <Check className="size-3.5" />}
              Accept Internship
            </Button>
            <Button
              size="sm"
              variant="outline"
              onClick={() => setPhase({ kind: "confirm", choice: "decline" })}
              disabled={working}
            >
              Decline
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}
