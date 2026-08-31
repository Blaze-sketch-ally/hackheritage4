import Link from "next/link";
import { ArrowRight, Building2, CheckCircle2, GraduationCap, School, Target } from "lucide-react";
import { Reveal } from "@/components/landing/reveal";

const ROLE_CARDS = [
  {
    label: "Students",
    icon: GraduationCap,
    accent: "from-indigo-500/15",
    points: [
      "Objective, question-bank-backed skill assessments",
      "Personalized skill gap analysis against real career roles",
      "A portfolio of projects and certifications recruiters actually see",
      "Explainable match scores for every job and internship",
    ],
  },
  {
    label: "Faculty",
    icon: Target,
    accent: "from-sky-500/15",
    points: [
      "Author assessment questions for your subject areas",
      "Peer-review questions to keep the bank rigorous",
      "Visibility into how students perform once assessments go live",
    ],
  },
  {
    label: "Industry",
    icon: Building2,
    accent: "from-emerald-500/15",
    points: [
      "Post jobs and internships with precise skill requirements",
      "Review applicants ranked by a real, explainable match score",
      "See portfolios and skill alignment side by side — not just a resume",
    ],
  },
  {
    label: "Institutions",
    icon: School,
    accent: "from-amber-500/15",
    points: [
      "Program-wide visibility into student skill development",
      "Placement and industry-partnership tracking in one place",
      "A stronger, evidence-backed story for accreditation and outcomes",
    ],
  },
] as const;

export function RolesSection() {
  return (
    <section id="roles" className="border-t border-border/60 bg-muted/30 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-indigo-600 uppercase">Built for everyone in the loop</p>
          <h2 className="mt-2 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            One platform, four perspectives
          </h2>
          <p className="mt-4 text-muted-foreground">
            Students, faculty, employers, and institutions all work from the same verified data — nobody is
            reading a stale spreadsheet.
          </p>
        </Reveal>

        <div className="mt-14 grid gap-5 sm:grid-cols-2">
          {ROLE_CARDS.map((role, i) => {
            const Icon = role.icon;
            return (
              <Reveal key={role.label} delay={i * 80}>
                <div className="group relative h-full overflow-hidden rounded-2xl border border-border/70 bg-background p-7 shadow-sm transition-all duration-300 hover:-translate-y-1 hover:shadow-lg hover:shadow-indigo-500/5">
                  <div
                    className={`pointer-events-none absolute -top-16 -right-16 size-40 rounded-full bg-gradient-to-br ${role.accent} to-transparent opacity-0 blur-2xl transition-opacity duration-300 group-hover:opacity-100`}
                    aria-hidden="true"
                  />
                  <div className="flex size-11 items-center justify-center rounded-xl bg-foreground/5 text-foreground transition-colors group-hover:bg-indigo-600 group-hover:text-white">
                    <Icon className="size-5" />
                  </div>
                  <h3 className="mt-5 text-lg font-semibold">{role.label}</h3>
                  <ul className="mt-4 space-y-2.5">
                    {role.points.map((point) => (
                      <li key={point} className="flex items-start gap-2 text-sm text-muted-foreground">
                        <CheckCircle2 className="mt-0.5 size-4 shrink-0 text-emerald-600" />
                        <span>{point}</span>
                      </li>
                    ))}
                  </ul>
                </div>
              </Reveal>
            );
          })}
        </div>

        <Reveal delay={200} className="mt-12 text-center">
          <Link
            href="/register"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-indigo-600 hover:underline"
          >
            Create your account
            <ArrowRight className="size-4" />
          </Link>
        </Reveal>
      </div>
    </section>
  );
}
