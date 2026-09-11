"use client";

import * as React from "react";
import Link from "next/link";
import {
  ArrowLeft,
  Award,
  BarChart3,
  Bell,
  Briefcase,
  Building2,
  CalendarDays,
  CheckCircle2,
  Clock,
  Compass,
  FileText,
  FlaskConical,
  GraduationCap,
  Layers,
  Lightbulb,
  Settings,
  ShieldCheck,
  Sparkles,
  Target,
  TrendingUp,
  Trophy,
  Users,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { toast } from "@/components/ui/sonner";
import { cn } from "@/lib/utils";

export type FeatureIconName =
  | "compass"
  | "sparkles"
  | "file-text"
  | "trending-up"
  | "bar-chart"
  | "trophy"
  | "calendar"
  | "settings"
  | "briefcase"
  | "graduation-cap"
  | "building"
  | "users"
  | "shield-check"
  | "award"
  | "research"
  | "target"
  | "layers"
  | "lightbulb";

const ICON_MAP = {
  compass: Compass,
  sparkles: Sparkles,
  "file-text": FileText,
  "trending-up": TrendingUp,
  "bar-chart": BarChart3,
  trophy: Trophy,
  calendar: CalendarDays,
  settings: Settings,
  briefcase: Briefcase,
  "graduation-cap": GraduationCap,
  building: Building2,
  users: Users,
  "shield-check": ShieldCheck,
  award: Award,
  research: FlaskConical,
  target: Target,
  layers: Layers,
  lightbulb: Lightbulb,
};

export interface FeatureRoadmapStubProps {
  title: string;
  badge?: string;
  role?: "Student" | "Faculty" | "Industry" | "Institution" | "Admin";
  description: string;
  highlights?: string[];
  backHref?: string;
  backLabel?: string;
  estimatedRelease?: string;
  iconName?: FeatureIconName;
  className?: string;
}

export function FeatureRoadmapStub({
  title,
  badge = "In Active Development",
  role = "Student",
  description,
  highlights = [
    "Integrated workflow with automated verification",
    "Real-time notifications & stage updates",
    "Exportable reports and verified audit trails",
  ],
  backHref,
  backLabel,
  estimatedRelease = "Q4 2026",
  iconName = "compass",
  className,
}: FeatureRoadmapStubProps) {
  const [notified, setNotified] = React.useState(false);

  const Icon = (iconName && ICON_MAP[iconName]) || Compass;

  const defaultBackHref =
    backHref ??
    (role === "Student"
      ? "/student/dashboard"
      : role === "Faculty"
      ? "/faculty/dashboard"
      : role === "Industry"
      ? "/industry/dashboard"
      : role === "Institution"
      ? "/institution/dashboard"
      : "/admin");

  const defaultBackLabel = backLabel ?? "Back to Dashboard";

  return (
    <div className={cn("mx-auto flex max-w-3xl flex-col gap-6 py-6 sm:py-10", className)}>
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          render={<Link href={defaultBackHref} />}
          nativeButton={false}
          className="gap-1.5 text-muted-foreground hover:text-foreground"
        >
          <ArrowLeft className="size-4" />
          {defaultBackLabel}
        </Button>
      </div>

      <Card className="relative overflow-hidden border-border/70 shadow-sm">
        <div className="absolute -right-16 -top-16 size-48 rounded-full bg-primary/5 blur-2xl" />
        <div className="absolute -left-16 -bottom-16 size-48 rounded-full bg-indigo-500/5 blur-2xl" />

        <CardHeader className="space-y-3 pb-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <div className="flex items-center gap-2.5">
              <div className="flex size-10 items-center justify-center rounded-xl bg-primary/10 text-primary">
                <Icon className="size-5" />
              </div>
              <div>
                <CardTitle className="text-xl sm:text-2xl font-semibold tracking-tight">
                  {title}
                </CardTitle>
                <span className="text-xs text-muted-foreground">{role} Portal Capability</span>
              </div>
            </div>

            <div className="flex items-center gap-2">
              <Badge variant="outline" className="gap-1 border-primary/30 text-xs font-medium">
                <Sparkles className="size-3 text-primary" />
                {badge}
              </Badge>
              <Badge variant="secondary" className="gap-1 text-xs text-muted-foreground">
                <Clock className="size-3" />
                {estimatedRelease}
              </Badge>
            </div>
          </div>

          <CardDescription className="text-sm leading-relaxed text-foreground/80 pt-1">
            {description}
          </CardDescription>
        </CardHeader>

        <CardContent className="space-y-6">
          {highlights.length > 0 && (
            <div className="rounded-xl border border-border/60 bg-muted/30 p-4">
              <h4 className="text-xs font-semibold tracking-wider text-muted-foreground uppercase mb-3">
                Planned Capabilities
              </h4>
              <ul className="grid gap-2.5 sm:grid-cols-2">
                {highlights.map((highlight, index) => (
                  <li key={index} className="flex items-start gap-2 text-xs sm:text-sm text-foreground/90">
                    <CheckCircle2 className="size-4 shrink-0 text-primary/70 mt-0.5" />
                    <span>{highlight}</span>
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex flex-wrap items-center justify-between gap-4 border-t border-border/60 pt-4">
            <div className="text-xs text-muted-foreground">
              We are building this feature in accordance with the portal development roadmap.
            </div>

            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setNotified(true);
                  toast.success(`You will be notified when ${title} is live!`);
                }}
                disabled={notified}
                className="gap-1.5"
              >
                {notified ? (
                  <>
                    <CheckCircle2 className="size-3.5 text-emerald-500" />
                    Notification Enabled
                  </>
                ) : (
                  <>
                    <Bell className="size-3.5" />
                    Notify Me When Live
                  </>
                )}
              </Button>

              <Button
                size="sm"
                render={<Link href={defaultBackHref} />}
                nativeButton={false}
              >
                {defaultBackLabel}
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
