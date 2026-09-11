"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Menu, Search, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { ThemeToggle } from "@/components/theme-toggle";
import { cn } from "@/lib/utils";

const NAV_LINKS = [
  { label: "How It Works", href: "#workflow" },
  { label: "Ecosystem Roles", href: "#roles" },
  { label: "Platform Standards", href: "#features" },
];

export function LandingNav() {
  const router = useRouter();
  const [scrolled, setScrolled] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    function onScroll() {
      setScrolled(window.scrollY > 8);
    }
    onScroll();
    window.addEventListener("scroll", onScroll, { passive: true });
    return () => window.removeEventListener("scroll", onScroll);
  }, []);

  // Global shortcut hint: if user presses Cmd+K on landing page, redirect to explore or login
  useEffect(() => {
    function onKeyDown(e: KeyboardEvent) {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        router.push("/login");
      }
    }
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [router]);

  return (
    <header
      className={cn(
        "fixed inset-x-0 top-0 z-50 transition-all duration-300",
        scrolled
          ? "border-b border-border/70 bg-background/85 backdrop-blur-md shadow-xs"
          : "border-b border-transparent bg-transparent",
      )}
    >
      <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-4 sm:px-6">
        {/* Brand Logo */}
        <Link href="/" className="flex items-center gap-2.5 font-bold tracking-tight">
          <span className="flex size-8 items-center justify-center rounded-lg bg-indigo-600 font-bold text-white shadow-md shadow-indigo-600/30">
            A
          </span>
          <span className="text-base text-foreground">AIC Portal</span>
          <span className="hidden sm:inline-flex items-center gap-1 rounded-full border border-border/80 bg-muted/40 px-2 py-0.5 text-[10px] font-semibold text-muted-foreground">
            <Sparkles className="size-2.5 text-indigo-600" />
            Enterprise
          </span>
        </Link>

        {/* Desktop Nav Links */}
        <nav className="hidden items-center gap-1 md:flex">
          {NAV_LINKS.map((link) => (
            <a
              key={link.href}
              href={link.href}
              className="rounded-lg px-3 py-1.5 text-sm font-medium text-foreground/70 transition-colors hover:bg-muted/70 hover:text-foreground"
            >
              {link.label}
            </a>
          ))}
        </nav>

        {/* Right CTA strip */}
        <div className="hidden items-center gap-2.5 md:flex">
          <button
            type="button"
            onClick={() => router.push("/login")}
            className="hidden lg:flex items-center gap-2 rounded-full border border-border/70 bg-muted/30 px-3 py-1.5 text-xs text-muted-foreground transition hover:border-indigo-600/40 hover:text-foreground"
            title="Press ⌘K to sign in"
          >
            <Search className="size-3.5" />
            <span>Search portal...</span>
            <kbd className="rounded border border-border bg-background px-1.5 py-0.5 font-mono text-[10px] text-muted-foreground">
              ⌘K
            </kbd>
          </button>

          <ThemeToggle />

          <Button
            variant="ghost"
            size="sm"
            className="text-sm font-medium text-foreground/80 hover:text-foreground"
            render={<Link href="/login" />}
            nativeButton={false}
          >
            Sign In
          </Button>
          <Button
            size="sm"
            className="bg-indigo-600 font-medium text-white shadow-xs hover:bg-indigo-600/90"
            render={<Link href="/register" />}
            nativeButton={false}
          >
            Get Started
          </Button>
        </div>

        {/* Mobile menu trigger */}
        <div className="flex items-center gap-2 md:hidden">
          <ThemeToggle />
          <button
            type="button"
            className="flex size-9 items-center justify-center rounded-lg border border-border/70 text-foreground/70 hover:bg-muted"
            aria-label={mobileOpen ? "Close menu" : "Open menu"}
            aria-expanded={mobileOpen}
            onClick={() => setMobileOpen((v) => !v)}
          >
            {mobileOpen ? <X className="size-5" /> : <Menu className="size-5" />}
          </button>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileOpen && (
        <div className="border-b border-border/70 bg-background/95 backdrop-blur-md px-4 pt-3 pb-5 md:hidden animate-in fade-in slide-in-from-top-2 duration-200">
          <nav className="flex flex-col gap-1">
            {NAV_LINKS.map((link) => (
              <a
                key={link.href}
                href={link.href}
                onClick={() => setMobileOpen(false)}
                className="rounded-lg px-3 py-2 text-sm font-medium text-foreground/80 hover:bg-muted"
              >
                {link.label}
              </a>
            ))}
          </nav>
          <div className="mt-4 flex flex-col gap-2 border-t border-border/60 pt-4">
            <Button
              variant="outline"
              className="w-full justify-center"
              render={<Link href="/login" />}
              nativeButton={false}
              onClick={() => setMobileOpen(false)}
            >
              Sign In
            </Button>
            <Button
              className="w-full justify-center bg-indigo-600 text-white hover:bg-indigo-600/90"
              render={<Link href="/register" />}
              nativeButton={false}
              onClick={() => setMobileOpen(false)}
            >
              Get Started Free
            </Button>
          </div>
        </div>
      )}
    </header>
  );
}
