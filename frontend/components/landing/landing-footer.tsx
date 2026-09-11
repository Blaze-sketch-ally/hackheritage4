import Link from "next/link";
import { ShieldCheck } from "lucide-react";
import { SkillBridgeBrand } from "@/components/branding/skillbridge-brand";

const FOOTER_LINKS = [
  { label: "Sign In", href: "/login" },
  { label: "Create Account", href: "/register" },
  { label: "Workflow", href: "#workflow" },
  { label: "Role Portals", href: "#roles" },
  { label: "Platform Standards", href: "#features" },
];

export function LandingFooter() {
  return (
    <footer className="border-t border-border/70 bg-muted/20">
      <div className="mx-auto max-w-6xl px-4 py-12 sm:px-6">
        <div className="flex flex-col items-center justify-between gap-6 sm:flex-row">
          <div className="flex items-center gap-3">
            <SkillBridgeBrand emblemSize={32} />
            <p className="text-xs text-muted-foreground">Academia-Industry Collaboration &amp; Skill Verification</p>
          </div>

          <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
            {FOOTER_LINKS.map((link) => (
              <Link
                key={link.href}
                href={link.href}
                className="text-xs font-medium text-muted-foreground transition-colors hover:text-foreground"
              >
                {link.label}
              </Link>
            ))}
          </nav>

          <div className="flex items-center gap-2 rounded-full border border-border/70 bg-background/80 px-3 py-1 text-[11px] font-medium text-muted-foreground">
            <span className="size-2 rounded-full bg-emerald-500 animate-pulse" />
            <span>Systems Operational</span>
          </div>
        </div>

        <div className="mt-8 flex flex-col items-center justify-between gap-4 border-t border-border/60 pt-6 text-center text-xs text-muted-foreground sm:flex-row sm:text-left">
          <div className="flex items-center gap-2">
            <ShieldCheck className="size-3.5 text-emerald-600 dark:text-emerald-400" />
            <span>Enterprise Multi-Tenant RLS · Verified Assessment Trust Network</span>
          </div>
          <p>
            &copy; {new Date().getFullYear()} SkillBridge. Ready for universal enterprise deployment.
          </p>
        </div>
      </div>
    </footer>
  );
}
