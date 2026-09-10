"use client";

import { useState } from "react";
import { AppHeader } from "@/components/layout/app-header";
import { FacultySidebar } from "@/components/faculty/faculty-sidebar";
import { NotificationBell } from "@/components/faculty/notifications/notification-bell";
import { FacultyCapabilitiesProvider } from "@/lib/faculty/capabilities";
import type { Profile } from "@/types/user";

/** Phase 1 (Faculty Dashboard Architecture): mounts
 * FacultyCapabilitiesProvider once per Faculty session, above both the
 * sidebar and the routed page content -- the single shared fetch of
 * GET /faculty/me/assessment-capabilities that both the capability-aware
 * sidebar and whichever dashboard (Connect/Question Studio/Evaluation
 * Workspace) is on screen consume, rather than each fetching it
 * independently. */
export function FacultyShell({ profile, children }: { profile: Profile; children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  return (
    <FacultyCapabilitiesProvider>
      <div className="flex min-h-screen bg-muted/30">
        <aside className="hidden w-64 shrink-0 border-r bg-card lg:block">
          <FacultySidebar />
        </aside>

        {mobileOpen ? (
          <div className="fixed inset-0 z-40 lg:hidden">
            <div
              className="absolute inset-0 bg-black/30"
              onClick={() => setMobileOpen(false)}
              aria-hidden="true"
            />
            <aside className="absolute inset-y-0 left-0 w-64 bg-card shadow-lg">
              <FacultySidebar onNavigate={() => setMobileOpen(false)} />
            </aside>
          </div>
        ) : null}

        <div className="flex min-w-0 flex-1 flex-col">
          <AppHeader
            profile={profile}
            onMenuClick={() => setMobileOpen(true)}
            profileHref="/faculty/profile"
            settingsHref="/faculty/settings"
            searchPlaceholder="Search questions, assessments..."
            notificationBell={<NotificationBell />}
          />
          <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
        </div>
      </div>
    </FacultyCapabilitiesProvider>
  );
}
