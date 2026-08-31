import Link from "next/link";

const FOOTER_LINKS = [
  { label: "Sign In", href: "/login" },
  { label: "Create Account", href: "/register" },
  { label: "Workflow", href: "#workflow" },
  { label: "Platform", href: "#features" },
];

export function LandingFooter() {
  return (
    <footer className="border-t border-border/60">
      <div className="mx-auto flex max-w-6xl flex-col items-center gap-6 px-4 py-12 sm:flex-row sm:justify-between sm:px-6">
        <div className="flex items-center gap-2">
          <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-600 text-xs text-white">
            A
          </span>
          <div>
            <p className="text-sm font-semibold">AIC Portal</p>
            <p className="text-xs text-muted-foreground">Academia-Industry Collaboration Portal</p>
          </div>
        </div>

        <nav className="flex flex-wrap items-center justify-center gap-x-6 gap-y-2">
          {FOOTER_LINKS.map((link) => (
            <Link
              key={link.href}
              href={link.href}
              className="text-sm text-muted-foreground transition-colors hover:text-foreground"
            >
              {link.label}
            </Link>
          ))}
        </nav>

        <p className="text-xs text-muted-foreground">
          &copy; {new Date().getFullYear()} AIC Portal. Built for students, faculty, and industry.
        </p>
      </div>
    </footer>
  );
}
