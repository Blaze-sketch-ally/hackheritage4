"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, Briefcase, CalendarDays, CheckCircle2, Clock, Landmark, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardAction, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getMyLinkRequests } from "@/lib/institution-links";
import { getMyInstitutionWorkspace, resolveStudentInstitutionLinkState } from "@/lib/student/institution";
import type { StudentInstitutionLinkState } from "@/lib/student/institution";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; link: StudentInstitutionLinkState };

function institutionDisplayName(name: string | null | undefined): string {
  const trimmed = name?.trim();
  return trimmed || "Your Institution";
}

/**
 * Small "My Institution" summary card for the Student Dashboard (Phase
 * 12, Step 13). Derives its state via resolveStudentInstitutionLinkState()
 * -- the SAME reconciliation the full My Institution page effectively
 * relies on -- from the same two existing sources: student_profiles.
 * institution_id (via GET /student/institution) and
 * institution_link_requests (via GET /institution-links/mine). No new
 * verification flag, and no second implementation of this logic.
 */
export function DashboardInstitution() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    void (async () => {
      try {
        const workspace = await getMyInstitutionWorkspace();
        if (cancelled) return;
        if (workspace.linked) {
          setState({ status: "ready", link: resolveStudentInstitutionLinkState(workspace, []) });
          return;
        }
        const { requests } = await getMyLinkRequests();
        if (cancelled) return;
        setState({ status: "ready", link: resolveStudentInstitutionLinkState(workspace, requests) });
      } catch {
        if (!cancelled) setState({ status: "error" });
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const link = state.status === "ready" ? state.link : null;
  const showViewAction = link?.kind === "VERIFIED" || link?.kind === "VERIFIED_AWAITING_SYNC";

  return (
    <Card>
      <CardHeader>
        <CardTitle>My Institution</CardTitle>
        {showViewAction ? (
          <CardAction>
            <Button variant="ghost" size="sm" render={<Link href="/student/institution" />} nativeButton={false}>
              View
            </Button>
          </CardAction>
        ) : null}
      </CardHeader>
      <CardContent>
        {state.status === "loading" ? <p className="text-sm text-muted-foreground">Loading…</p> : null}

        {state.status === "error" ? (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <AlertCircle className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">Couldn&apos;t load your institution.</p>
            <Button variant="outline" size="sm" onClick={() => setReloadKey((k) => k + 1)}>
              Try again
            </Button>
          </div>
        ) : null}

        {link?.kind === "NOT_CONNECTED" ? (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <Landmark className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm font-medium">Connect to your Institution</p>
            <p className="text-xs text-muted-foreground">
              Link your account to your college or university to see its placement drives, internships and events.
            </p>
            <Button size="sm" className="mt-1" render={<Link href="/student/institution" />} nativeButton={false}>
              Find My Institution
            </Button>
          </div>
        ) : null}

        {link?.kind === "PENDING" ? (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <Clock className="size-6 text-amber-600 dark:text-amber-400" aria-hidden="true" />
            <p className="text-sm font-medium">
              {link.institutionName ? `${link.institutionName} — Verification Pending` : "Institution verification pending"}
            </p>
            <p className="text-xs text-muted-foreground">
              Your institution connection is awaiting TPO approval.
            </p>
          </div>
        ) : null}

        {link?.kind === "REJECTED" ? (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <Landmark className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm font-medium">
              {link.institutionName ? `${link.institutionName} declined your request` : "Your institution request was declined"}
            </p>
            <Button size="sm" className="mt-1" render={<Link href="/student/institution" />} nativeButton={false}>
              Find My Institution
            </Button>
          </div>
        ) : null}

        {link?.kind === "VERIFIED_AWAITING_SYNC" ? (
          <div className="space-y-2">
            <div className="space-y-1">
              <p className="text-base font-semibold leading-6">{institutionDisplayName(link.institutionName)}</p>
              <Badge variant="default" className="gap-1">
                <CheckCircle2 className="size-3.5" aria-hidden="true" /> Verified
              </Badge>
            </div>
            <p className="text-xs text-muted-foreground">
              Your connection is approved. Full institution details will appear here shortly.
            </p>
          </div>
        ) : null}

        {link?.kind === "VERIFIED" ? (
          <div className="space-y-3">
            <div className="space-y-1">
              <p className="text-base font-semibold leading-6">
                {institutionDisplayName(link.workspace.institution?.institution_name)}
              </p>
              <Badge variant="default" className="gap-1">
                <CheckCircle2 className="size-3.5" aria-hidden="true" /> Verified
              </Badge>
            </div>
            <div className="grid grid-cols-3 gap-2 text-center text-xs">
              <div className="flex flex-col items-center gap-1 rounded-lg bg-muted/50 px-2 py-2">
                <Briefcase className="size-4 text-indigo-600 dark:text-indigo-400" aria-hidden="true" />
                <span className="font-semibold tabular-nums">{link.workspace.kpis.placement_drives}</span>
                <span className="text-muted-foreground">Drives</span>
              </div>
              <div className="flex flex-col items-center gap-1 rounded-lg bg-muted/50 px-2 py-2">
                <Sparkles className="size-4 text-violet-600 dark:text-violet-400" aria-hidden="true" />
                <span className="font-semibold tabular-nums">{link.workspace.kpis.internships}</span>
                <span className="text-muted-foreground">Internships</span>
              </div>
              <div className="flex flex-col items-center gap-1 rounded-lg bg-muted/50 px-2 py-2">
                <CalendarDays className="size-4 text-blue-600 dark:text-blue-400" aria-hidden="true" />
                <span className="font-semibold tabular-nums">{link.workspace.kpis.events}</span>
                <span className="text-muted-foreground">Events</span>
              </div>
            </div>
          </div>
        ) : null}
      </CardContent>
    </Card>
  );
}
