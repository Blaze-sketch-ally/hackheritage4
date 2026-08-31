"use client";

import { useEffect, useState } from "react";
import {
  Award,
  Briefcase,
  ClipboardCheck,
  Layers,
  LineChart,
  TrendingUp,
} from "lucide-react";
import { Reveal } from "@/components/landing/reveal";
import { cn } from "@/lib/utils";

const STEPS = [
  {
    title: "Assess",
    icon: ClipboardCheck,
    summary: "Take a randomized, question-bank-backed assessment for any skill in the catalog.",
    detail:
      "Every attempt draws a fresh, blueprint-governed set of questions and is scored automatically the moment you submit — no self-grading, no guesswork.",
  },
  {
    title: "Discover Gaps",
    icon: TrendingUp,
    summary: "See exactly where you stand against real career-role requirements.",
    detail:
      "Your assessment results are compared against the skill requirements of career roles you're interested in, surfacing concrete, actionable gaps — not vague advice.",
  },
  {
    title: "Build Portfolio",
    icon: Layers,
    summary: "Showcase the projects and certifications that assessment scores can't capture.",
    detail:
      "Projects and certifications sit alongside your verified skills, giving recruiters the full picture — context an assessment alone can't provide.",
  },
  {
    title: "Get Matched",
    icon: Briefcase,
    summary: "Browse jobs and internships with a real, explainable match score for each.",
    detail:
      "Every opportunity lists its actual skill requirements, and your match score is computed live from your own assessment evidence — never a black box.",
  },
  {
    title: "Apply",
    icon: Award,
    summary: "Apply in one click and track every application's status in one place.",
    detail:
      "No spreadsheets, no cold emails into the void — your application status updates as the employer reviews it, end to end.",
  },
  {
    title: "Get Hired",
    icon: LineChart,
    summary: "Employers review applicants ranked by match, alongside your portfolio.",
    detail:
      "Recruiters see your skill alignment, strengths, gaps, and portfolio together — the same explainable score you saw, not a hidden algorithm.",
  },
] as const;

export function WorkflowSection() {
  const [active, setActive] = useState(0);
  const [paused, setPaused] = useState(false);

  useEffect(() => {
    if (paused) return;
    const id = window.setInterval(() => {
      setActive((i) => (i + 1) % STEPS.length);
    }, 4200);
    return () => window.clearInterval(id);
  }, [paused]);

  const step = STEPS[active];
  const StepIcon = step.icon;

  return (
    <section id="workflow" className="relative py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-indigo-600 uppercase">How it works</p>
          <h2 className="mt-2 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            One coherent pipeline, end to end
          </h2>
          <p className="mt-4 text-muted-foreground">
            Six real, connected stages — not six disconnected features. What you prove in step one is what
            gets you matched in step four.
          </p>
        </Reveal>

        <Reveal delay={100} className="mt-14">
          <div
            className="grid gap-8 lg:grid-cols-[1fr_1.1fr] lg:items-center"
            onMouseEnter={() => setPaused(true)}
            onMouseLeave={() => setPaused(false)}
          >
            {/* Step selector */}
            <ol className="relative flex flex-col gap-1">
              <div
                className="absolute top-0 left-[19px] w-px bg-border"
                style={{ height: `calc(${STEPS.length - 1} * 100% / ${STEPS.length})` }}
                aria-hidden="true"
              />
              {STEPS.map((s, i) => {
                const Icon = s.icon;
                const isActive = i === active;
                return (
                  <li key={s.title}>
                    <button
                      type="button"
                      onClick={() => setActive(i)}
                      aria-current={isActive}
                      className={cn(
                        "group relative flex w-full items-center gap-3.5 rounded-lg px-2.5 py-3 text-left transition-colors",
                        isActive ? "bg-indigo-500/8" : "hover:bg-muted",
                      )}
                    >
                      <span
                        className={cn(
                          "z-10 flex size-10 shrink-0 items-center justify-center rounded-full border-2 bg-background transition-colors",
                          isActive ? "border-indigo-600 text-indigo-600" : "border-border text-muted-foreground",
                        )}
                      >
                        <Icon className="size-4.5" />
                      </span>
                      <div className="min-w-0">
                        <p className={cn("text-sm font-semibold", isActive ? "text-foreground" : "text-foreground/80")}>
                          {i + 1}. {s.title}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">{s.summary}</p>
                      </div>
                    </button>
                  </li>
                );
              })}
            </ol>

            {/* Active step detail panel */}
            <div
              key={step.title}
              className="relative overflow-hidden rounded-2xl border border-border/70 bg-gradient-to-br from-indigo-500/5 via-background to-emerald-500/5 p-8 shadow-sm transition-all duration-300 sm:p-10"
            >
              <div className="flex size-12 items-center justify-center rounded-xl bg-indigo-600 text-white shadow-sm shadow-indigo-600/30">
                <StepIcon className="size-6" />
              </div>
              <p className="mt-6 text-xs font-semibold tracking-wide text-indigo-600 uppercase">
                Step {active + 1} of {STEPS.length}
              </p>
              <h3 className="mt-1.5 text-2xl font-semibold tracking-tight">{step.title}</h3>
              <p className="mt-3 text-[15px] leading-relaxed text-muted-foreground">{step.detail}</p>

              <div className="mt-8 flex gap-1.5" role="presentation">
                {STEPS.map((s, i) => (
                  <span
                    key={s.title}
                    className={cn(
                      "h-1 flex-1 overflow-hidden rounded-full bg-border transition-colors",
                      i === active && "bg-indigo-200",
                    )}
                  >
                    {i === active && (
                      <span
                        key={`${step.title}-${paused}`}
                        className={cn("block h-full rounded-full bg-indigo-600", !paused && "animate-[landing-progress_4.2s_linear]")}
                        style={paused ? { width: "100%" } : undefined}
                      />
                    )}
                  </span>
                ))}
              </div>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
