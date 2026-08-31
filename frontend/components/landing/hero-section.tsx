"use client";

import { useState } from "react";
import Link from "next/link";
import { ArrowRight, Building2, GraduationCap, School, Sparkles, Target } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const ROLES = [
  {
    key: "student",
    label: "Student",
    icon: GraduationCap,
    blurb: "Take real assessments, see your verified skill gaps, build a portfolio, and get matched to roles you actually qualify for.",
  },
  {
    key: "faculty",
    label: "Faculty",
    icon: Target,
    blurb: "Author and review assessment questions, keep the skill catalog rigorous, and see how your students are performing.",
  },
  {
    key: "industry",
    label: "Industry",
    icon: Building2,
    blurb: "Post jobs and internships, define the skills you actually need, and review applicants ranked by an explainable match score.",
  },
  {
    key: "institution",
    label: "Institution",
    icon: School,
    blurb: "Track placement outcomes and skill trends across your student body, and strengthen ties with hiring partners.",
  },
] as const;

export function HeroSection() {
  const [activeRole, setActiveRole] = useState<(typeof ROLES)[number]["key"]>("student");
  const role = ROLES.find((r) => r.key === activeRole)!;

  return (
    <section className="relative overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-28">
      {/* Ambient animated background -- pure CSS, no canvas/library. */}
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden="true">
        <div
          className="absolute top-[-10%] left-[8%] size-[32rem] rounded-full bg-indigo-500/20 blur-3xl animate-landing-blob"
          style={{ animationDelay: "-4s" }}
        />
        <div
          className="absolute top-[10%] right-[4%] size-[26rem] rounded-full bg-emerald-400/15 blur-3xl animate-landing-blob"
          style={{ animationDelay: "-9s" }}
        />
        <div
          className="absolute inset-x-0 top-0 h-full opacity-[0.35] animate-landing-grid"
          style={{
            backgroundImage:
              "linear-gradient(to right, var(--border) 1px, transparent 1px), linear-gradient(to bottom, var(--border) 1px, transparent 1px)",
            backgroundSize: "64px 64px",
            maskImage: "radial-gradient(ellipse 60% 50% at 50% 0%, black 40%, transparent 90%)",
          }}
        />
      </div>

      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <div className="mx-auto max-w-3xl text-center">
          <div className="mx-auto mb-6 flex w-fit items-center gap-1.5 rounded-full border border-border/70 bg-background/80 px-3 py-1 text-xs font-medium text-foreground/70 shadow-sm backdrop-blur">
            <Sparkles className="size-3.5 text-indigo-600" />
            Academia × Industry, finally connected
          </div>

          <h1 className="text-balance text-4xl font-semibold tracking-tight sm:text-5xl md:text-6xl">
            Prove your skills.
            <br />
            <span className="bg-gradient-to-r from-indigo-600 via-indigo-500 to-emerald-500 bg-clip-text text-transparent">
              Not just claim them.
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-balance text-base text-muted-foreground sm:text-lg">
            AIC Portal replaces resume keywords with real, assessed evidence — objective skill scoring,
            explainable job matching, and a recruitment pipeline both students and employers can actually
            trust.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button
              size="lg"
              className="h-11 gap-2 bg-indigo-600 px-6 text-[15px] text-white hover:bg-indigo-600/90"
              render={<Link href="/register" />}
              nativeButton={false}
            >
              Get Started Free
              <ArrowRight className="size-4 transition-transform group-hover/button:translate-x-0.5" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="h-11 px-6 text-[15px]"
              render={<Link href="/login" />}
              nativeButton={false}
            >
              Sign In
            </Button>
          </div>
        </div>

        {/* Interactive role switcher */}
        <div className="mx-auto mt-16 max-w-3xl">
          <p className="mb-3 text-center text-xs font-semibold tracking-wide text-muted-foreground uppercase">
            I am a...
          </p>
          <div className="flex flex-wrap items-center justify-center gap-2">
            {ROLES.map((r) => {
              const Icon = r.icon;
              const active = r.key === activeRole;
              return (
                <button
                  key={r.key}
                  type="button"
                  onClick={() => setActiveRole(r.key)}
                  aria-pressed={active}
                  className={cn(
                    "flex items-center gap-1.5 rounded-full border px-4 py-2 text-sm font-medium transition-all",
                    active
                      ? "border-indigo-600 bg-indigo-600 text-white shadow-sm shadow-indigo-600/25"
                      : "border-border/70 bg-background/70 text-foreground/70 backdrop-blur hover:border-indigo-600/40 hover:text-foreground",
                  )}
                >
                  <Icon className="size-4" />
                  {r.label}
                </button>
              );
            })}
          </div>
          <div
            key={role.key}
            className="mx-auto mt-5 max-w-xl rounded-xl border border-border/70 bg-background/70 px-5 py-4 text-center text-sm text-muted-foreground shadow-sm backdrop-blur transition-all duration-300"
          >
            {role.blurb}
          </div>
        </div>
      </div>
    </section>
  );
}
