import { Check, X } from "lucide-react";
import { Reveal } from "@/components/landing/reveal";

const OLD_WAY = [
  "Skills are whatever the resume claims",
  "Keyword-matching filters out real candidates",
  "Recruiters can't see why someone was shortlisted",
  "Students find out they're underqualified after rejection",
];

const NEW_WAY = [
  "Skills are backed by a scored, randomized assessment",
  "Matching is computed from real requirements vs. real evidence",
  "Every match score is visible and explainable to both sides",
  "Skill gaps are visible before you ever apply",
];

export function ComparisonSection() {
  return (
    <section className="border-t border-border/60 py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Reveal className="mx-auto max-w-2xl text-center">
          <p className="text-sm font-semibold tracking-wide text-indigo-600 uppercase">
            Why it&apos;s different
          </p>
          <h2 className="mt-2 text-balance text-3xl font-semibold tracking-tight sm:text-4xl">
            Resumes claim. AIC Portal proves.
          </h2>
        </Reveal>

        <div className="mt-14 grid gap-5 md:grid-cols-2">
          <Reveal>
            <div className="h-full rounded-2xl border border-border/70 bg-muted/40 p-8">
              <p className="text-sm font-semibold text-muted-foreground">The old way</p>
              <ul className="mt-5 space-y-4">
                {OLD_WAY.map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm text-muted-foreground">
                    <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-foreground/10">
                      <X className="size-3" />
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>

          <Reveal delay={120}>
            <div className="relative h-full overflow-hidden rounded-2xl border-2 border-indigo-600/50 bg-gradient-to-br from-indigo-500/5 via-background to-emerald-500/5 p-8 shadow-sm">
              <p className="text-sm font-semibold text-indigo-600">The AIC Portal way</p>
              <ul className="mt-5 space-y-4">
                {NEW_WAY.map((item) => (
                  <li key={item} className="flex items-start gap-3 text-sm font-medium">
                    <span className="mt-0.5 flex size-5 shrink-0 items-center justify-center rounded-full bg-emerald-600 text-white">
                      <Check className="size-3" />
                    </span>
                    {item}
                  </li>
                ))}
              </ul>
            </div>
          </Reveal>
        </div>
      </div>
    </section>
  );
}
