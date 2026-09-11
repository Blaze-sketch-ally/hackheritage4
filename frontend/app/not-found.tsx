import Link from "next/link";
import { Compass, Home, KeyRound, Sparkles } from "lucide-react";
import { Button } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-background px-4 text-center">
      {/* Ambient background glow */}
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden="true">
        <div className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 size-96 rounded-full bg-indigo-500/10 blur-3xl" />
      </div>

      <div className="mx-auto max-w-md space-y-6">
        <div className="mx-auto flex size-14 items-center justify-center rounded-2xl border border-border/80 bg-muted/30 text-indigo-600 shadow-sm dark:text-indigo-400">
          <Compass className="size-7 animate-spin-slow" />
        </div>

        <div className="space-y-2">
          <div className="inline-flex items-center gap-1.5 rounded-full border border-border/70 bg-muted/40 px-3 py-1 text-xs font-semibold uppercase tracking-wider text-muted-foreground">
            <Sparkles className="size-3 text-indigo-600" />
            404 Error · Resource Not Found
          </div>
          <h1 className="text-3xl font-bold tracking-tight sm:text-4xl">
            We couldn&apos;t find this page
          </h1>
          <p className="text-sm text-muted-foreground leading-relaxed">
            The page you requested may have been moved, archived, or requires role authentication.
            Use the links below to safely return to the portal.
          </p>
        </div>

        <div className="flex flex-col items-center justify-center gap-2.5 sm:flex-row">
          <Button
            size="default"
            className="w-full gap-2 bg-indigo-600 text-white shadow-xs hover:bg-indigo-600/90 sm:w-auto"
            render={<Link href="/" />}
            nativeButton={false}
          >
            <Home className="size-4" />
            Back to Home
          </Button>
          <Button
            variant="outline"
            size="default"
            className="w-full gap-2 sm:w-auto"
            render={<Link href="/login" />}
            nativeButton={false}
          >
            <KeyRound className="size-4" />
            Sign In to Workspace
          </Button>
        </div>

        <div className="pt-4 border-t border-border/60">
          <p className="text-xs text-muted-foreground">
            Looking for public career roles or internships?{" "}
            <Link
              href="/opportunities/jobs"
              className="font-medium text-indigo-600 underline-offset-4 hover:underline dark:text-indigo-400"
            >
              Explore Public Opportunities &rarr;
            </Link>
          </p>
        </div>
      </div>
    </div>
  );
}
