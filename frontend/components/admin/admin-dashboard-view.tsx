"use client";

import Link from "next/link";
import {
  Activity,
  ArrowRight,
  BadgeCheck,
  Building2,
  CheckCircle2,
  ClipboardCheck,
  GraduationCap,
  Landmark,
  Layers,
  Server,
  ShieldCheck,
  Sparkles,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { StatCard } from "@/components/dashboard/stat-card";

export function AdminDashboardView() {
  return (
    <div className="space-y-8">
      <div>
        <div className="flex items-center gap-2">
          <Badge className="bg-slate-800 text-white hover:bg-slate-800 dark:bg-slate-700">
            System Core
          </Badge>
          <span className="text-xs text-muted-foreground">Admin Console · Telemetry</span>
        </div>
        <h1 className="mt-1 text-2xl font-bold tracking-tight text-foreground">
          Platform Governance &amp; Telemetry
        </h1>
        <p className="text-sm text-muted-foreground">
          Real-time oversight of multi-tenant security, faculty assessment capabilities, and institution verification.
        </p>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard
          label="Governance Engine"
          value="Operational"
          helperText="RLS & Role Boundaries Active"
          icon={ShieldCheck}
          accent="emerald"
        />
        <StatCard
          label="Assessment Pipeline"
          value="Active"
          helperText="Objective & AI-Evaluated Queues"
          icon={ClipboardCheck}
          accent="indigo"
        />
        <StatCard
          label="Multi-Tenant Auth"
          value="Secured"
          helperText="Supabase JWT & Role Claims"
          icon={Server}
          accent="violet"
        />
        <StatCard
          label="Institutional Queue"
          value="Protected"
          helperText="Cross-Tenant Verification Active"
          icon={BadgeCheck}
          accent="blue"
        />
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <ShieldCheck className="size-5 text-slate-700 dark:text-slate-300" />
              Active Governance Consoles
            </CardTitle>
            <CardDescription>
              Authoritative admin workflows configured for platform integrity.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between rounded-lg border p-3.5 transition-colors hover:bg-muted/40">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold">Faculty Assessment Permissions</p>
                  <Badge variant="outline" className="text-[10px] text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                    Live
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  Grant, suspend, or revoke Faculty assessment authoring &amp; review privileges.
                </p>
              </div>
              <Button size="sm" variant="outline" render={<Link href="/admin/faculty" />}>
                Manage <ArrowRight className="size-3.5" />
              </Button>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3.5 transition-colors hover:bg-muted/40">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold">Evaluator Assignments</p>
                  <Badge variant="outline" className="text-[10px] text-emerald-600 dark:text-emerald-400 border-emerald-500/30">
                    Live
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  Assign qualified faculty evaluators to subjective and AI questions in student attempts.
                </p>
              </div>
              <Button size="sm" variant="outline" render={<Link href="/admin/assessments" />}>
                Assign <ArrowRight className="size-3.5" />
              </Button>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3.5 transition-colors hover:bg-muted/40">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold">Institutional Verification</p>
                  <Badge variant="secondary" className="text-[10px]">
                    Roadmap
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  Review and verify partner colleges, polytechnics, and educational bodies.
                </p>
              </div>
              <Button size="sm" variant="ghost" render={<Link href="/admin/verification" />}>
                View Queue
              </Button>
            </div>

            <div className="flex items-center justify-between rounded-lg border p-3.5 transition-colors hover:bg-muted/40">
              <div className="space-y-0.5">
                <div className="flex items-center gap-2">
                  <p className="text-sm font-semibold">Opportunity Moderation</p>
                  <Badge variant="secondary" className="text-[10px]">
                    Roadmap
                  </Badge>
                </div>
                <p className="text-xs text-muted-foreground">
                  Content screening and moderation for public jobs and internship postings.
                </p>
              </div>
              <Button size="sm" variant="ghost" render={<Link href="/admin/opportunities" />}>
                Moderation
              </Button>
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base flex items-center gap-2">
              <Activity className="size-5 text-slate-700 dark:text-slate-300" />
              Platform Infrastructure Health
            </CardTitle>
            <CardDescription>
              Core subsystem operational telemetry and service connectivity.
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-3">
            <div className="flex items-center justify-between rounded-lg bg-muted/40 p-3">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" />
                <div>
                  <p className="text-sm font-medium">Supabase Auth Gateway</p>
                  <p className="text-xs text-muted-foreground">Session Token Signing &amp; Rotation</p>
                </div>
              </div>
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 text-[11px]">
                Healthy
              </Badge>
            </div>

            <div className="flex items-center justify-between rounded-lg bg-muted/40 p-3">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" />
                <div>
                  <p className="text-sm font-medium">FastAPI Application Core</p>
                  <p className="text-xs text-muted-foreground">Uvicorn ASGI Gateway (Port 8000)</p>
                </div>
              </div>
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 text-[11px]">
                Active
              </Badge>
            </div>

            <div className="flex items-center justify-between rounded-lg bg-muted/40 p-3">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" />
                <div>
                  <p className="text-sm font-medium">Row-Level Security (RLS)</p>
                  <p className="text-xs text-muted-foreground">Tenant-Isolated Access Rules</p>
                </div>
              </div>
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 text-[11px]">
                Enforced
              </Badge>
            </div>

            <div className="flex items-center justify-between rounded-lg bg-muted/40 p-3">
              <div className="flex items-center gap-3">
                <CheckCircle2 className="size-4 text-emerald-600 dark:text-emerald-400" />
                <div>
                  <p className="text-sm font-medium">Assessment Scoring Worker</p>
                  <p className="text-xs text-muted-foreground">Objective Automated Calculation</p>
                </div>
              </div>
              <Badge variant="outline" className="bg-emerald-500/10 text-emerald-700 dark:text-emerald-400 border-emerald-500/20 text-[11px]">
                Ready
              </Badge>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-4">
        <h2 className="text-base font-semibold">Domain Registries</h2>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <Link
            href="/admin/students"
            className="group flex flex-col justify-between rounded-xl border bg-card p-4 transition-all hover:border-slate-400 hover:shadow-sm"
          >
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <GraduationCap className="size-5 text-indigo-600 dark:text-indigo-400" />
                <Badge variant="outline" className="text-[10px]">Registry</Badge>
              </div>
              <p className="font-semibold text-foreground group-hover:text-primary">Student Registry</p>
              <p className="text-xs text-muted-foreground">
                Verified enrollment, academic records, and portfolio audits.
              </p>
            </div>
            <span className="mt-3 text-xs font-medium text-primary flex items-center gap-1">
              Explore <ArrowRight className="size-3" />
            </span>
          </Link>

          <Link
            href="/admin/companies"
            className="group flex flex-col justify-between rounded-xl border bg-card p-4 transition-all hover:border-slate-400 hover:shadow-sm"
          >
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <Building2 className="size-5 text-violet-600 dark:text-violet-400" />
                <Badge variant="outline" className="text-[10px]">Registry</Badge>
              </div>
              <p className="font-semibold text-foreground group-hover:text-primary">Corporate Partners</p>
              <p className="text-xs text-muted-foreground">
                Employer brand verification, recruiter accounts, and hiring compliance.
              </p>
            </div>
            <span className="mt-3 text-xs font-medium text-primary flex items-center gap-1">
              Explore <ArrowRight className="size-3" />
            </span>
          </Link>

          <Link
            href="/admin/institutions"
            className="group flex flex-col justify-between rounded-xl border bg-card p-4 transition-all hover:border-slate-400 hover:shadow-sm"
          >
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <Landmark className="size-5 text-blue-600 dark:text-blue-400" />
                <Badge variant="outline" className="text-[10px]">Registry</Badge>
              </div>
              <p className="font-semibold text-foreground group-hover:text-primary">Partner Institutions</p>
              <p className="text-xs text-muted-foreground">
                Affiliated colleges, university domains, and placement cells.
              </p>
            </div>
            <span className="mt-3 text-xs font-medium text-primary flex items-center gap-1">
              Explore <ArrowRight className="size-3" />
            </span>
          </Link>

          <Link
            href="/admin/skills"
            className="group flex flex-col justify-between rounded-xl border bg-card p-4 transition-all hover:border-slate-400 hover:shadow-sm"
          >
            <div className="space-y-1">
              <div className="flex items-center justify-between">
                <Layers className="size-5 text-emerald-600 dark:text-emerald-400" />
                <Badge variant="outline" className="text-[10px]">Ontology</Badge>
              </div>
              <p className="font-semibold text-foreground group-hover:text-primary">Skill Taxonomy</p>
              <p className="text-xs text-muted-foreground">
                Standardized competency frameworks, skill graphs, and tagging.
              </p>
            </div>
            <span className="mt-3 text-xs font-medium text-primary flex items-center gap-1">
              Explore <ArrowRight className="size-3" />
            </span>
          </Link>
        </div>
      </div>
    </div>
  );
}
