"use client";

import { useState } from "react";
import { IndustryHeader } from "@/components/industry/industry-header";
import { IndustrySidebar } from "@/components/industry/industry-sidebar";
import { MobileNavOverlay } from "@/components/layout/mobile-nav-overlay";
import type { Profile } from "@/types/user";

// Same architecture as components/student/student-shell.tsx: a fixed
// desktop sidebar, a slide-over drawer on mobile, and a sticky header
// above a padded <main>. Reused by app/industry/layout.tsx for every
// /industry/* route.
export function IndustryShell({ profile, children }: { profile: Profile; children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-muted/30">
      <aside className="hidden w-64 shrink-0 border-r bg-card lg:block">
        <IndustrySidebar />
      </aside>

      <MobileNavOverlay open={mobileOpen} onClose={() => setMobileOpen(false)}>
        <IndustrySidebar onNavigate={() => setMobileOpen(false)} />
      </MobileNavOverlay>

      <div className="flex min-w-0 flex-1 flex-col">
        <IndustryHeader profile={profile} onMenuClick={() => setMobileOpen(true)} />
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
