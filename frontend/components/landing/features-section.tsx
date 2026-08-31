import {
  BarChart3,
  ClipboardCheck,
  Layers,
  ShieldCheck,
  Target,
  Zap,
} from "lucide-react";
import { Reveal } from "@/components/landing/reveal";

const FEATURES = [
  {
    icon: ClipboardCheck,
    title: "Randomized, Scored Assessments",
    description: "A real question bank with peer-reviewed questions and blueprint-governed, randomized attempts — scored the instant you submit.",
  },
  {
    icon: Target,
    title: "Career-Role Skill Gap Analysis",
    description: "Your assessment evidence compared against the real skill requirements of the roles you care about — no guesswork, no vague advice.",
  },
  {
    icon: Layers,
    title: "Digital Portfolio",
    description: "Projects and certifications alongside your verified skills, giving reviewers full context an assessment score alone can't give.",
  },
  {
    icon: Zap,
    title: "Explainable Matching",
    description: "Every match score is computed live from real skill evidence against real requirements — visible to both sides, never a black box.",
  },
  {
    icon: BarChart3,
    title: "End-to-End Application Tracking",
    description: "Apply, then watch status move from Applied to Shortlisted to Selected — one source of truth for every application.",
  },
  {
    icon: ShieldCheck,
    title: "Secure by Design",
    description: "Row-level security enforces every boundary at the database — a student's data stays a student's, an employer only ever sees legitimate applicants.",
  },
] as const;

export function FeaturesSection() {
  return (
    <section id="features" className="py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-indigo-600 uppercase">The platform</p>
          <h2 className="mt-2 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            Everything real, nothing simulated
          </h2>
          <p className="mt-4 text-muted-foreground">
            Every capability below is a live feature backed by a real database — not a mockup standing in
            for a future release.
          </p>
        </Reveal>

        <div className="mt-14 grid gap-5 sm:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map((feature, i) => {
            const Icon = feature.icon;
            return (
              <Reveal key={feature.title} delay={(i % 3) * 90}>
                <div className="group h-full rounded-2xl border border-border/70 bg-background p-6 transition-all duration-300 hover:-translate-y-1 hover:border-indigo-600/30 hover:shadow-lg hover:shadow-indigo-500/5">
                  <div className="flex size-10 items-center justify-center rounded-lg bg-indigo-500/10 text-indigo-600 transition-transform duration-300 group-hover:scale-110">
                    <Icon className="size-5" />
                  </div>
                  <h3 className="mt-4 text-base font-semibold">{feature.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-muted-foreground">{feature.description}</p>
                </div>
              </Reveal>
            );
          })}
        </div>
      </div>
    </section>
  );
}
