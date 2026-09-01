"use client";

import { useState } from "react";
import { InstitutionHeader } from "@/components/institution/institution-header";
import { InstitutionSidebar } from "@/components/institution/institution-sidebar";
import type { Profile } from "@/types/user";

// Same architecture as components/industry/industry-shell.tsx and
// components/student/student-shell.tsx: a fixed desktop sidebar, a slide-over
// drawer on mobile, and a sticky header (which carries the Sign out action)
// above a padded <main>. Reused by app/institution/layout.tsx for every
// /institution/* route.
export function InstitutionShell({ profile, children }: { profile: Profile; children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-muted/30">
      <aside className="hidden w-64 shrink-0 border-r bg-card lg:block">
        <InstitutionSidebar />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute inset-y-0 left-0 w-64 bg-card shadow-lg">
            <InstitutionSidebar onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <InstitutionHeader profile={profile} onMenuClick={() => setMobileOpen(true)} />
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
