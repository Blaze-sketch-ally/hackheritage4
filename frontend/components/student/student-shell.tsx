"use client";

import { useEffect, useState } from "react";
import { StudentHeader } from "@/components/student/student-header";
import { StudentSidebar } from "@/components/student/student-sidebar";
import { listMyJobTraining } from "@/lib/student/job-training";
import type { Profile } from "@/types/user";

export function StudentShell({ profile, children }: { profile: Profile; children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false);

  // One call per student page load to decide whether the "Job Training"
  // nav item shows. Best-effort: any failure just leaves it hidden -- the
  // route and backend still enforce access, so a hidden-but-reachable nav
  // item is a UX gap, never a security one. The authoritative signal is an
  // accessible enrollment, NEVER application.status.
  const [hasJobTraining, setHasJobTraining] = useState(false);
  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const { enrollments } = await listMyJobTraining();
        if (!cancelled) setHasJobTraining(enrollments.length > 0);
      } catch {
        if (!cancelled) setHasJobTraining(false);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, []);

  return (
    <div className="flex min-h-screen bg-muted/30">
      <aside className="hidden w-64 shrink-0 border-r bg-card lg:block">
        <StudentSidebar hasJobTraining={hasJobTraining} />
      </aside>

      {mobileOpen ? (
        <div className="fixed inset-0 z-40 lg:hidden">
          <div
            className="absolute inset-0 bg-black/30"
            onClick={() => setMobileOpen(false)}
            aria-hidden="true"
          />
          <aside className="absolute inset-y-0 left-0 w-64 bg-card shadow-lg">
            <StudentSidebar
              hasJobTraining={hasJobTraining}
              onNavigate={() => setMobileOpen(false)}
            />
          </aside>
        </div>
      ) : null}

      <div className="flex min-w-0 flex-1 flex-col">
        <StudentHeader profile={profile} onMenuClick={() => setMobileOpen(true)} />
        <main className="min-w-0 flex-1 p-4 sm:p-6 lg:p-8">{children}</main>
      </div>
    </div>
  );
}
