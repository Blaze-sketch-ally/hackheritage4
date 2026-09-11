"use client";

import { useState } from "react";
import Link from "next/link";
import {
  ArrowRight,
  Award,
  BarChart3,
  BookOpen,
  Briefcase,
  Building2,
  CheckCircle2,
  ChevronRight,
  ExternalLink,
  GraduationCap,
  Layers,
  School,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  UserCheck,
  Users,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const STATS = [
  { value: "50,000+", label: "Verified Assessments", hint: "Scored deterministically" },
  { value: "1,200+", label: "Corporate Openings", hint: "With verified skill blueprints" },
  { value: "94.8%", label: "Match Precision", hint: "Explainable skill scoring" },
  { value: "4 Roles", label: "Unified Ecosystem", hint: "Zero manual spreadsheets" },
] as const;

const ROLES = [
  {
    key: "student",
    label: "Student",
    icon: GraduationCap,
    tagline: "Verified Skills & Explainable Matching",
    blurb: "Take real assessments, see your verified skill gaps, build a portfolio, and get matched to roles you actually qualify for.",
  },
  {
    key: "faculty",
    label: "Faculty",
    icon: Target,
    tagline: "Peer-Reviewed Question Authoring",
    blurb: "Author and review assessment questions, keep the skill catalog rigorous, and see how your students are performing.",
  },
  {
    key: "industry",
    label: "Industry",
    icon: Building2,
    tagline: "Skill-Ranked Candidate Pipeline",
    blurb: "Post jobs and internships, define the skills you actually need, and review applicants ranked by an explainable match score.",
  },
  {
    key: "institution",
    label: "Institution",
    icon: School,
    tagline: "Accreditation & Placement Telemetry",
    blurb: "Track placement outcomes and skill trends across your student body, and strengthen ties with hiring partners.",
  },
] as const;

export function HeroSection() {
  const [activeRole, setActiveRole] = useState<(typeof ROLES)[number]["key"]>("student");
  const role = ROLES.find((r) => r.key === activeRole)!;

  return (
    <section className="relative overflow-hidden pt-32 pb-20 sm:pt-40 sm:pb-28">
      {/* Ambient animated background */}
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden" aria-hidden="true">
        <div
          className="absolute top-[-10%] left-[8%] size-[34rem] rounded-full bg-indigo-500/15 blur-3xl animate-landing-blob"
          style={{ animationDelay: "-4s" }}
        />
        <div
          className="absolute top-[10%] right-[4%] size-[28rem] rounded-full bg-emerald-400/10 blur-3xl animate-landing-blob"
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
        {/* Main Headline */}
        <div className="mx-auto max-w-3xl text-center">
          <div className="mx-auto mb-6 flex w-fit items-center gap-2 rounded-full border border-border/80 bg-background/80 px-3.5 py-1.5 text-xs font-medium text-foreground/80 shadow-xs backdrop-blur-md">
            <span className="flex size-2 rounded-full bg-emerald-500 animate-pulse" />
            <Sparkles className="size-3.5 text-indigo-600 dark:text-indigo-400" />
            <span>The Trust Engine for Modern Academic Hiring</span>
          </div>

          <h1 className="text-balance text-4xl font-bold tracking-tight sm:text-5xl md:text-6xl">
            Prove your skills.
            <br />
            <span className="bg-gradient-to-r from-indigo-600 via-indigo-500 to-emerald-500 bg-clip-text text-transparent">
              Not just claim them.
            </span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-balance text-base text-muted-foreground sm:text-lg">
            SkillBridge bridges students, universities, and enterprise recruiters with randomized,
            peer-reviewed assessments, explainable job matches, and tamper-proof portfolio evidence.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <Button
              size="lg"
              className="h-11 gap-2 bg-indigo-600 px-6 text-[15px] font-medium text-white shadow-md shadow-indigo-600/20 hover:bg-indigo-600/90"
              render={<Link href="/register" />}
              nativeButton={false}
            >
              Get Started Free
              <ArrowRight className="size-4 transition-transform group-hover/button:translate-x-0.5" />
            </Button>
            <Button
              size="lg"
              variant="outline"
              className="h-11 px-6 text-[15px] font-medium"
              render={<Link href="/login" />}
              nativeButton={false}
            >
              Sign In to Workspace
            </Button>
          </div>
        </div>

        {/* Enterprise Telemetry Metric Strip */}
        <div className="mx-auto mt-14 max-w-4xl rounded-2xl border border-border/70 bg-background/60 p-4 shadow-xs backdrop-blur-md">
          <div className="grid grid-cols-2 gap-4 divide-y divide-border/60 sm:grid-cols-4 sm:divide-y-0 sm:divide-x">
            {STATS.map((stat) => (
              <div key={stat.label} className="px-3 pt-2 text-center sm:pt-0">
                <p className="text-2xl font-bold tracking-tight text-foreground sm:text-3xl">
                  {stat.value}
                </p>
                <p className="text-xs font-semibold text-foreground/80">{stat.label}</p>
                <p className="mt-0.5 text-[11px] text-muted-foreground">{stat.hint}</p>
              </div>
            ))}
          </div>
        </div>

        {/* Interactive Live Role Switcher & Dynamic Preview Console */}
        <div className="mx-auto mt-16 max-w-4xl">
          <div className="flex flex-col items-center justify-center gap-2 text-center">
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
              Explore Live Workspace Capabilities
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
                      "flex items-center gap-2 rounded-full border px-4 py-2 text-sm font-medium transition-all",
                      active
                        ? "border-indigo-600 bg-indigo-600 text-white shadow-md shadow-indigo-600/25"
                        : "border-border/80 bg-background/80 text-foreground/70 backdrop-blur hover:border-indigo-600/40 hover:text-foreground",
                    )}
                  >
                    <Icon className="size-4" />
                    <span>{r.label}</span>
                  </button>
                );
              })}
            </div>
            <p className="mt-1 text-xs text-muted-foreground">
              {role.tagline} — {role.blurb}
            </p>
          </div>

          {/* Simulated Live Workspace Cockpit Window */}
          <div className="mt-6 overflow-hidden rounded-2xl border border-border/80 bg-background shadow-xl">
            {/* Window Topbar */}
            <div className="flex items-center justify-between border-b border-border/70 bg-muted/40 px-4 py-3">
              <div className="flex items-center gap-2">
                <span className="size-3 rounded-full bg-rose-500/80" />
                <span className="size-3 rounded-full bg-amber-500/80" />
                <span className="size-3 rounded-full bg-emerald-500/80" />
                <span className="ml-2 font-mono text-xs text-muted-foreground">
                  skillbridge://workspace/{activeRole}
                </span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2.5 py-0.5 text-[11px] font-medium text-emerald-600 dark:text-emerald-400">
                  <span className="size-1.5 rounded-full bg-emerald-500" />
                  Live Verified Session
                </span>
              </div>
            </div>

            {/* Dynamic Content Per Role */}
            <div className="p-5 sm:p-6">
              {activeRole === "student" && (
                <div className="grid gap-6 md:grid-cols-2">
                  {/* Student Left Column: Verified Skills */}
                  <div className="space-y-4 rounded-xl border border-border/70 bg-muted/20 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Award className="size-4 text-indigo-600 dark:text-indigo-400" />
                        <span className="text-sm font-semibold">Verified Skill Radar</span>
                      </div>
                      <span className="text-[11px] font-medium text-muted-foreground">3 Assessments Scored</span>
                    </div>

                    <div className="space-y-3">
                      <div>
                        <div className="flex justify-between text-xs">
                          <span className="font-medium">Distributed Systems & Concurrency</span>
                          <span className="font-semibold text-indigo-600 dark:text-indigo-400">96% (Top 4%)</span>
                        </div>
                        <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-indigo-600" style={{ width: "96%" }} />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between text-xs">
                          <span className="font-medium">Algorithms & Data Structures</span>
                          <span className="font-semibold text-emerald-600 dark:text-emerald-400">92% (Advanced)</span>
                        </div>
                        <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-emerald-600" style={{ width: "92%" }} />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between text-xs">
                          <span className="font-medium">Cloud Architecture (Kubernetes & Go)</span>
                          <span className="font-semibold text-indigo-600 dark:text-indigo-400">88% (Proficient)</span>
                        </div>
                        <div className="mt-1.5 h-2 w-full overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-indigo-600" style={{ width: "88%" }} />
                        </div>
                      </div>
                    </div>

                    <div className="rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-2.5 text-[11px] text-muted-foreground">
                      <strong className="font-medium text-foreground">Verified Certificate #AIC-9821:</strong> Scored deterministically via randomized questions. Zero self-reported claims.
                    </div>
                  </div>

                  {/* Student Right Column: Explainable Job Match */}
                  <div className="space-y-4 rounded-xl border border-indigo-500/30 bg-gradient-to-br from-indigo-500/5 via-background to-emerald-500/5 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Briefcase className="size-4 text-emerald-600 dark:text-emerald-400" />
                        <span className="text-sm font-semibold">Live Explainable Match</span>
                      </div>
                      <span className="rounded-full bg-emerald-600/10 px-2 py-0.5 text-xs font-bold text-emerald-600 dark:text-emerald-400">
                        94% Match
                      </span>
                    </div>

                    <div>
                      <p className="text-sm font-semibold text-foreground">Cloud Platform Infrastructure Engineer</p>
                      <p className="text-xs text-muted-foreground">Stripe / Enterprise Partner · San Francisco / Remote</p>
                    </div>

                    <div className="space-y-1.5 text-xs text-muted-foreground">
                      <div className="flex items-center gap-2 text-foreground">
                        <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400" />
                        <span>Core Distributed Assessment: <strong>+48% match weight</strong></span>
                      </div>
                      <div className="flex items-center gap-2 text-foreground">
                        <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400" />
                        <span>Verified Open-Source Raft Project: <strong>+30% match weight</strong></span>
                      </div>
                      <div className="flex items-center gap-2 text-foreground">
                        <CheckCircle2 className="size-3.5 text-emerald-600 dark:text-emerald-400" />
                        <span>Cloud Architecture Score: <strong>+16% match weight</strong></span>
                      </div>
                    </div>

                    <div className="flex items-center justify-between pt-1">
                      <span className="text-[11px] text-muted-foreground">Missing: gRPC Protocol Buffers (+6%)</span>
                      <Button size="xs" variant="outline" className="text-xs font-medium" render={<Link href="/register" />} nativeButton={false}>
                        Practice Assessment
                        <ChevronRight className="size-3" />
                      </Button>
                    </div>
                  </div>
                </div>
              )}

              {activeRole === "faculty" && (
                <div className="grid gap-6 md:grid-cols-2">
                  {/* Faculty Left Column */}
                  <div className="space-y-4 rounded-xl border border-border/70 bg-muted/20 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <BookOpen className="size-4 text-sky-600 dark:text-sky-400" />
                        <span className="text-sm font-semibold">Question Authoring Studio</span>
                      </div>
                      <span className="rounded-full bg-sky-500/10 px-2 py-0.5 text-xs font-medium text-sky-600 dark:text-sky-400">
                        Peer Review Stage
                      </span>
                    </div>

                    <div className="rounded-lg border border-border/60 bg-background p-3">
                      <p className="text-xs font-medium text-foreground">
                        &quot;Lock-Free Ring Buffers &amp; Concurrent Memory Fences in C++20&quot;
                      </p>
                      <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-muted-foreground">
                        <span className="rounded bg-muted px-1.5 py-0.5">Bloom: Evaluate (Level 5)</span>
                        <span className="rounded bg-muted px-1.5 py-0.5">Difficulty: 0.85 (Hard)</span>
                        <span className="text-emerald-600 dark:text-emerald-400 font-medium">3/3 Approvals</span>
                      </div>
                    </div>

                    <div className="space-y-1.5 text-xs text-muted-foreground">
                      <p className="font-medium text-foreground">Peer Reviewers on Record:</p>
                      <div className="flex items-center justify-between text-[11px]">
                        <span>Prof. Aris Thorne (MIT)</span>
                        <span className="text-emerald-600 font-medium">Approved · Clean Rubric</span>
                      </div>
                      <div className="flex items-center justify-between text-[11px]">
                        <span>Dr. Elena Rostova (Stanford)</span>
                        <span className="text-emerald-600 font-medium">Approved · Validated Tests</span>
                      </div>
                    </div>
                  </div>

                  {/* Faculty Right Column */}
                  <div className="space-y-4 rounded-xl border border-border/70 bg-muted/20 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <TrendingUp className="size-4 text-emerald-600 dark:text-emerald-400" />
                        <span className="text-sm font-semibold">Cohort Telemetry (CS401)</span>
                      </div>
                      <span className="text-xs font-medium text-emerald-600 dark:text-emerald-400">+8.4% YoY</span>
                    </div>

                    <div className="grid grid-cols-2 gap-3">
                      <div className="rounded-lg border border-border/60 bg-background p-3 text-center">
                        <p className="text-xl font-bold text-foreground">148</p>
                        <p className="text-[11px] text-muted-foreground">Attempts Scored</p>
                      </div>
                      <div className="rounded-lg border border-border/60 bg-background p-3 text-center">
                        <p className="text-xl font-bold text-emerald-600 dark:text-emerald-400">82.4%</p>
                        <p className="text-[11px] text-muted-foreground">Median Score</p>
                      </div>
                    </div>

                    <p className="text-xs text-muted-foreground">
                      Assessment blueprints dynamically generate a randomized 20-question challenge per student from the certified question bank.
                    </p>

                    <Button size="sm" variant="outline" className="w-full text-xs" render={<Link href="/register" />} nativeButton={false}>
                      Create Subject Blueprint
                      <ArrowRight className="size-3" />
                    </Button>
                  </div>
                </div>
              )}

              {activeRole === "industry" && (
                <div className="grid gap-6 md:grid-cols-2">
                  {/* Industry Left Column */}
                  <div className="space-y-4 rounded-xl border border-border/70 bg-muted/20 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <UserCheck className="size-4 text-emerald-600 dark:text-emerald-400" />
                        <span className="text-sm font-semibold">Applicant Ranking Pipeline</span>
                      </div>
                      <span className="text-xs font-medium text-muted-foreground">42 Evaluated</span>
                    </div>

                    <div className="space-y-2">
                      <div className="flex items-center justify-between rounded-lg border border-emerald-500/30 bg-emerald-500/5 p-2.5">
                        <div>
                          <p className="text-xs font-semibold text-foreground">Sarah Lin (97% Match)</p>
                          <p className="text-[11px] text-muted-foreground">Go · Distributed Systems · Raft</p>
                        </div>
                        <span className="rounded bg-emerald-600 px-2 py-0.5 text-[11px] font-bold text-white">
                          Shortlisted
                        </span>
                      </div>

                      <div className="flex items-center justify-between rounded-lg border border-border/60 bg-background p-2.5">
                        <div>
                          <p className="text-xs font-semibold text-foreground">Devon Brooks (91% Match)</p>
                          <p className="text-[11px] text-muted-foreground">Rust · Tokio · Microservices</p>
                        </div>
                        <span className="rounded bg-muted px-2 py-0.5 text-[11px] font-medium text-muted-foreground">
                          Screening
                        </span>
                      </div>
                    </div>

                    <p className="text-[11px] text-muted-foreground">
                      No keyword guessing: Applicants are ranked strictly by objective assessment test performance and verified projects.
                    </p>
                  </div>

                  {/* Industry Right Column */}
                  <div className="space-y-4 rounded-xl border border-border/70 bg-muted/20 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <Layers className="size-4 text-indigo-600 dark:text-indigo-400" />
                        <span className="text-sm font-semibold">Explainable Scoring Weights</span>
                      </div>
                      <span className="text-xs text-muted-foreground">Transparent</span>
                    </div>

                    <div className="space-y-2 text-xs">
                      <div className="flex justify-between">
                        <span>Assessment Question Banks</span>
                        <strong className="text-foreground">50%</strong>
                      </div>
                      <div className="flex justify-between">
                        <span>Verified Project Code &amp; Repos</span>
                        <strong className="text-foreground">30%</strong>
                      </div>
                      <div className="flex justify-between">
                        <span>Academic Foundations &amp; Certs</span>
                        <strong className="text-foreground">20%</strong>
                      </div>
                    </div>

                    <div className="rounded-lg border border-indigo-500/20 bg-indigo-500/5 p-2.5 text-[11px] text-muted-foreground">
                      Both recruiters and students see the identical breakdown. Zero proprietary algorithmic bias or hidden disqualifications.
                    </div>

                    <Button size="sm" className="w-full bg-indigo-600 text-xs text-white hover:bg-indigo-600/90" render={<Link href="/register" />} nativeButton={false}>
                      Post Verified Job Opening
                      <ArrowRight className="size-3" />
                    </Button>
                  </div>
                </div>
              )}

              {activeRole === "institution" && (
                <div className="grid gap-6 md:grid-cols-2">
                  {/* Institution Left Column */}
                  <div className="space-y-4 rounded-xl border border-border/70 bg-muted/20 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <School className="size-4 text-amber-600 dark:text-amber-400" />
                        <span className="text-sm font-semibold">Placement &amp; Outcomes Telemetry</span>
                      </div>
                      <span className="text-xs font-semibold text-emerald-600 dark:text-emerald-400">91.4% Rate</span>
                    </div>

                    <div className="space-y-2.5">
                      <div>
                        <div className="flex justify-between text-xs">
                          <span>Computer Science &amp; Engineering</span>
                          <span className="font-semibold text-foreground">94.8% Placed</span>
                        </div>
                        <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-amber-500" style={{ width: "94.8%" }} />
                        </div>
                      </div>

                      <div>
                        <div className="flex justify-between text-xs">
                          <span>Information Systems</span>
                          <span className="font-semibold text-foreground">89.2% Placed</span>
                        </div>
                        <div className="mt-1 h-2 w-full overflow-hidden rounded-full bg-muted">
                          <div className="h-full rounded-full bg-amber-500" style={{ width: "89.2%" }} />
                        </div>
                      </div>
                    </div>

                    <div className="flex items-center gap-3 pt-1 text-xs text-muted-foreground">
                      <span className="flex items-center gap-1">
                        <Users className="size-3.5 text-foreground" /> 1,420 Cohort Size
                      </span>
                      <span className="flex items-center gap-1">
                        <Building2 className="size-3.5 text-foreground" /> 68 Hiring Partners
                      </span>
                    </div>
                  </div>

                  {/* Institution Right Column */}
                  <div className="space-y-4 rounded-xl border border-border/70 bg-muted/20 p-4">
                    <div className="flex items-center justify-between">
                      <div className="flex items-center gap-2">
                        <BarChart3 className="size-4 text-indigo-600 dark:text-indigo-400" />
                        <span className="text-sm font-semibold">Accreditation Audit Export</span>
                      </div>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-[11px] font-medium text-muted-foreground">
                        ABET &amp; NAAC Ready
                      </span>
                    </div>

                    <p className="text-xs text-muted-foreground leading-relaxed">
                      Generate tamper-proof audit trails for ABET Student Outcomes (1-5) and NAAC Criterion 5.2 (Student Progression) directly from verified assessment scores.
                    </p>

                    <div className="rounded-lg border border-border/70 bg-background p-3 text-xs">
                      <div className="flex items-center justify-between">
                        <span className="font-medium">2026 Accreditation Audit Log</span>
                        <span className="flex items-center gap-1 text-emerald-600 font-semibold text-[11px]">
                          <ShieldCheck className="size-3.5" /> Certified
                        </span>
                      </div>
                      <p className="mt-1 text-[11px] text-muted-foreground">Includes 42,000+ deterministic assessment timestamp signatures.</p>
                    </div>

                    <Button size="sm" variant="outline" className="w-full text-xs" render={<Link href="/register" />} nativeButton={false}>
                      Export Accreditation Report
                      <ExternalLink className="size-3" />
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      </div>
    </section>
  );
}
