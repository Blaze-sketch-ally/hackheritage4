"use client";

import { useState } from "react";
import { AppHeader } from "@/components/layout/app-header";
import { IndustrySidebar } from "@/components/industry/industry-sidebar";
import type { Profile } from "@/types/user";

export function IndustryShell({ profile, children }: { profile: Profile; children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-muted/30">
      <aside className="hidden w-64 shrink-0 border-r bg-card lg:block">
        <IndustrySidebar />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute inset-y-0 left-0 w-64 bg-card shadow-lg">
            <IndustrySidebar onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader
          profile={profile}
          onMenuClick={() => setMobileOpen(true)}
          profileHref="/industry/profile"
          settingsHref="/industry/settings"
          searchPlaceholder="Search candidates, postings..."
        />
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
