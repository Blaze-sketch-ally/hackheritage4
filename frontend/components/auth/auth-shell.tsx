import Link from "next/link";
import { cn } from "@/lib/utils";

interface AuthShellProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  /** Override the card's max-width — e.g. a wider grid for onboarding. Defaults to "max-w-sm". */
  contentClassName?: string;
}

/** Shared branded layout for every (auth) page: logo, card, heading. */
export function AuthShell({ title, description, children, contentClassName }: AuthShellProps) {
  return (
    <div className="flex min-h-screen flex-col items-center justify-center bg-muted/30 px-4 py-10">
      <div className="mb-8 flex flex-col items-center gap-1 text-center">
        <Link href="/" className="text-lg font-semibold tracking-tight">
          AIC Portal
        </Link>
        <p className="text-xs text-muted-foreground">Academia-Industry Collaboration</p>
      </div>

      <div
        className={cn(
          "w-full max-w-sm rounded-xl bg-card p-6 shadow-sm ring-1 ring-foreground/10 sm:p-8",
          contentClassName,
        )}
      >
        <div className="mb-6 space-y-1 text-center">
          <h1 className="text-xl font-semibold">{title}</h1>
          {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
        </div>
        {children}
      </div>
    </div>
  );
}
