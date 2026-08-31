import Link from "next/link";
import { ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Reveal } from "@/components/landing/reveal";

export function CtaSection() {
  return (
    <section className="py-24 sm:py-32">
      <div className="mx-auto max-w-6xl px-4 sm:px-6">
        <Reveal>
          <div className="relative overflow-hidden rounded-3xl border border-border/70 bg-gradient-to-br from-indigo-600 via-indigo-600 to-indigo-700 px-6 py-16 text-center shadow-xl shadow-indigo-600/20 sm:px-16 sm:py-20">
            <div
              className="pointer-events-none absolute -top-24 -right-24 size-72 rounded-full bg-white/10 blur-3xl"
              aria-hidden="true"
            />
            <div
              className="pointer-events-none absolute -bottom-24 -left-24 size-72 rounded-full bg-emerald-400/20 blur-3xl"
              aria-hidden="true"
            />

            <h2 className="relative text-balance text-3xl font-semibold tracking-tight text-white sm:text-4xl">
              Ready to prove what you can actually do?
            </h2>
            <p className="relative mx-auto mt-4 max-w-xl text-balance text-indigo-100">
              Join as a student to get assessed and matched, or as an employer to hire on real evidence.
              Setup takes minutes.
            </p>
            <div className="relative mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
              <Button
                size="lg"
                className="h-11 gap-2 bg-white px-6 text-[15px] text-indigo-700 hover:bg-white/90"
                render={<Link href="/register" />}
                nativeButton={false}
              >
                Create Your Account
                <ArrowRight className="size-4" />
              </Button>
              <Button
                size="lg"
                variant="ghost"
                className="h-11 px-6 text-[15px] text-white hover:bg-white/10 hover:text-white"
                render={<Link href="/login" />}
                nativeButton={false}
              >
                I already have an account
              </Button>
            </div>
          </div>
        </Reveal>
      </div>
    </section>
  );
}
