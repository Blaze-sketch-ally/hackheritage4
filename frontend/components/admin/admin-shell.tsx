"use client";

import { useState } from "react";
import { AppHeader } from "@/components/layout/app-header";
import { AdminSidebar } from "@/components/admin/admin-sidebar";
import type { Profile } from "@/types/user";

export function AdminShell({ profile, children }: { profile: Profile; children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <div className="flex min-h-screen bg-muted/30">
      <aside className="hidden w-64 shrink-0 border-r bg-card lg:block">
        <AdminSidebar />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute inset-y-0 left-0 w-64 bg-card shadow-lg">
            <AdminSidebar onNavigate={() => setMobileOpen(false)} />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <AppHeader
          profile={profile}
          onMenuClick={() => setMobileOpen(true)}
          profileHref="/admin/settings"
          settingsHref="/admin/settings"
          searchPlaceholder="Search governance, users, capabilities..."
        />
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
