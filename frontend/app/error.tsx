"use client";

import { useEffect } from "react";
import Link from "next/link";
import { AlertTriangle, Home, RefreshCcw, ShieldAlert } from "lucide-react";
import { Button } from "@/components/ui/button";

interface ErrorPageProps {
  error: Error & { digest?: string };
  reset: () => void;
}

export default function ErrorPage({ error, reset }: ErrorPageProps) {
  useEffect(() => {
    console.error("Uncaught application error:", error);
  }, [error]);

  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 text-center">
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden="true">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 size-96 rounded-full bg-rose-500/10 blur-3xl" />
      </div>

      <div className="mx-auto max-w-md space-y-6">
        <div className="mx-auto flex size-14 items-center justify-center rounded-2xl border border-rose-500/20 bg-rose-500/10 text-rose-600 shadow-sm dark:text-rose-400">
          <AlertTriangle className="size-7" />
        </div>

        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-rose-500/20 bg-rose-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-rose-700 dark:text-rose-300">
            <ShieldAlert className="size-3" />
            Application Exception
          </div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            Something unexpected occurred
          </h1>
          <p className="text-sm text-muted-foreground leading-relaxed">
            {error.message || "An unexpected system error occurred while rendering this view. Our telemetry has captured this event."}
          </p>
          {error.digest && (
            <p className="font-mono text-[11px] text-muted-foreground">
              Error Reference Digest: {error.digest}
            </p>
          )}
        </div>

        <div className="flex flex-col items-center justify-center gap-2.5 sm:flex-row">
          <Button
            onClick={() => reset()}
            className="w-full gap-2 bg-indigo-600 text-white shadow-xs hover:bg-indigo-600/90 sm:w-auto"
          >
            <RefreshCcw className="size-4" />
            Try Again
          </Button>
          <Button
            variant="outline"
            className="w-full gap-2 sm:w-auto"
            render={<Link href="/" />}
            nativeButton={false}
          >
            <Home className="size-4" />
            Return Home
          </Button>
        </div>
      </div>
    </div>
  );
}
