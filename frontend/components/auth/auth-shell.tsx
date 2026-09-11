"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  ArrowLeft,
  CheckCircle2,
  Lock,
  ShieldCheck,
  Sparkles,
  GraduationCap,
  Building2,
  School,
  Target,
} from "lucide-react";
import { ThemeToggle } from "@/components/theme-toggle";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface AuthShellProps {
  title: string;
  description?: string;
  children: React.ReactNode;
  /** Override the card's max-width — e.g. a wider grid for onboarding. Defaults to "max-w-sm". */
  contentClassName?: string;
}

const ROLE_PILLS = [
  { label: "Student", icon: GraduationCap, color: "text-indigo-500" },
  { label: "Faculty", icon: Target, color: "text-emerald-500" },
  { label: "Industry", icon: Building2, color: "text-violet-500" },
  { label: "Institution", icon: School, color: "text-blue-500" },
];

export function AuthShell({ title, description, children, contentClassName }: AuthShellProps) {
  const pathname = usePathname();
  const isOnboarding = contentClassName?.includes("max-w-2xl");

  return (
    <div className="relative flex min-h-screen flex-col bg-background text-foreground">
      {/* Background ambient lighting */}
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden="true">
        <div className="absolute -top-40 left-1/4 size-[32rem] rounded-full bg-indigo-500/10 blur-3xl dark:bg-indigo-500/15" />
        <div className="absolute top-1/2 -right-40 size-[28rem] rounded-full bg-emerald-500/10 blur-3xl dark:bg-emerald-500/10" />
      </div>

      {/* Top Navbar */}
      <header className="sticky top-0 z-30 flex h-16 w-full items-center justify-between border-b border-border/40 bg-background/80 px-4 backdrop-blur-md sm:px-8">
        <div className="flex items-center gap-3">
          <Link href="/" className="group flex items-center gap-2.5">
            <span className="flex size-8 items-center justify-center rounded-lg bg-indigo-600 text-sm font-bold text-white shadow-sm shadow-indigo-600/30 transition-transform group-hover:scale-105">
              A
            </span>
            <div className="flex flex-col">
              <span className="text-base font-semibold tracking-tight text-foreground">AIC Portal</span>
              <span className="hidden text-[10px] text-muted-foreground sm:inline">
                Academia × Industry
              </span>
            </div>
          </Link>
        </div>

        <div className="flex items-center gap-2">
          <Link
            href="/"
            className="hidden items-center gap-1 text-xs font-medium text-muted-foreground transition-colors hover:text-foreground sm:flex"
          >
            <ArrowLeft className="size-3.5" /> Back to Home
          </Link>
          <div className="h-4 w-px bg-border/60 mx-1 hidden sm:block" />
          <ThemeToggle />
        </div>
      </header>

      {/* Main Content Area */}
      <main className="flex flex-1 items-center justify-center p-4 sm:p-6 lg:p-10">
        {isOnboarding ? (
          // Centered wide card for role selection / onboarding
          <div
            className={cn(
              "w-full rounded-2xl border border-border/70 bg-card/90 p-6 shadow-xl backdrop-blur-xl ring-1 ring-foreground/5 sm:p-10",
              contentClassName,
            )}
          >
            <div className="mb-8 space-y-1.5 text-center">
              <h1 className="text-2xl font-bold tracking-tight sm:text-3xl">{title}</h1>
              {description ? <p className="text-sm text-muted-foreground">{description}</p> : null}
            </div>
            {children}
          </div>
        ) : (
          // Modern dual-pane container for Login / Register / Password Reset
          <div className="grid w-full max-w-5xl gap-8 lg:grid-cols-12 lg:items-center">
            {/* Form Column */}
            <div className="flex justify-center lg:col-span-6 xl:col-span-7">
              <div
                className={cn(
                  "w-full max-w-md rounded-2xl border border-border/70 bg-card/90 p-6 shadow-xl backdrop-blur-xl ring-1 ring-foreground/5 sm:p-8",
                  contentClassName,
                )}
              >
                {/* Role badges indicator */}
                <div className="mb-6 flex flex-wrap items-center justify-center gap-1.5 rounded-xl border border-border/50 bg-muted/40 p-1.5 text-xs">
                  {ROLE_PILLS.map((r) => {
                    const Icon = r.icon;
                    return (
                      <span
                        key={r.label}
                        className="flex items-center gap-1 rounded-lg px-2 py-0.5 text-[11px] font-medium text-muted-foreground"
                      >
                        <Icon className={cn("size-3", r.color)} />
                        {r.label}
                      </span>
                    );
                  })}
                </div>

                <div className="mb-6 space-y-1.5 text-center">
                  <h1 className="text-2xl font-bold tracking-tight">{title}</h1>
                  {description ? (
                    <p className="text-sm text-muted-foreground">{description}</p>
                  ) : null}
                </div>

                {children}

                <div className="mt-8 border-t border-border/50 pt-4 text-center">
                  <p className="flex items-center justify-center gap-1.5 text-[11px] text-muted-foreground">
                    <Lock className="size-3 text-emerald-600 dark:text-emerald-400" />
                    256-bit Encrypted Session · Strict Row-Level Security
                  </p>
                </div>
              </div>
            </div>

            {/* Feature Showcase Column (Desktop Only) */}
            <div className="hidden flex-col gap-6 lg:flex lg:col-span-6 xl:col-span-5">
              <div className="space-y-3">
                <Badge className="bg-indigo-600/10 text-indigo-700 dark:bg-indigo-500/20 dark:text-indigo-300 border-indigo-500/20 hover:bg-indigo-600/15 text-xs w-fit">
                  <Sparkles className="size-3 mr-1" />
                  Objective Skill Verification
                </Badge>
                <h2 className="text-3xl font-bold tracking-tight text-foreground">
                  The Trust Engine for Modern Academic Hiring.
                </h2>
                <p className="text-sm text-muted-foreground">
                  Connect genuine skills to real opportunities. No keyword inflation, no black-box screening, just verified competency.
                </p>
              </div>

              <div className="space-y-3">
                <div className="flex items-start gap-3 rounded-xl border border-border/60 bg-card/60 p-3.5 backdrop-blur-sm">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-600 dark:text-indigo-400">
                    <CheckCircle2 className="size-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">Question-Bank Backed</h3>
                    <p className="text-xs text-muted-foreground">
                      Objective assessments authored and verified by university faculty.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 rounded-xl border border-border/60 bg-card/60 p-3.5 backdrop-blur-sm">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 text-emerald-600 dark:text-emerald-400">
                    <CheckCircle2 className="size-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">Explainable Match Score</h3>
                    <p className="text-xs text-muted-foreground">
                      See exact skill proficiencies, strengths, and requirements for every job and internship.
                    </p>
                  </div>
                </div>

                <div className="flex items-start gap-3 rounded-xl border border-border/60 bg-card/60 p-3.5 backdrop-blur-sm">
                  <div className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-violet-500/10 text-violet-600 dark:text-violet-400">
                    <CheckCircle2 className="size-4" />
                  </div>
                  <div>
                    <h3 className="text-sm font-semibold text-foreground">Four Connected Stakeholders</h3>
                    <p className="text-xs text-muted-foreground">
                      Students, faculty, corporate employers, and campus placement cells on one shared truth.
                    </p>
                  </div>
                </div>
              </div>

              <div className="rounded-xl border border-dashed border-border/70 p-4 text-xs text-muted-foreground">
                <p className="italic">
                  &ldquo;AIC Portal replaces subjective resumes with verified evidence — saving our recruitment team hundreds of screening hours.&rdquo;
                </p>
                <p className="mt-2 font-semibold text-foreground">
                  — Campus Talent Acquisition Lead
                </p>
              </div>
            </div>
          </div>
        )}
      </main>

      {/* Footer */}
      <footer className="border-t border-border/40 py-4 text-center text-xs text-muted-foreground">
        © {new Date().getFullYear()} AIC Portal. Built for Academia, Industry &amp; Higher Education.
      </footer>
    </div>
  );
}
