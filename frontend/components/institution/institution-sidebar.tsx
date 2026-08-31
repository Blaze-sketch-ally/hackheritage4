"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Building2,
  CalendarDays,
  ClipboardCheck,
  FileText,
  Handshake,
  LayoutDashboard,
  type LucideIcon,
  Settings,
  TrendingDown,
  Trophy,
  User,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href?: string;
  icon: LucideIcon;
}

interface NavGroup {
  label?: string;
  items: NavItem[];
}

// Every href below points at a route that already exists in
// app/institution/ (some are scaffold placeholder pages, linked anyway —
// matching the convention already established in the other sidebars).
const NAV_GROUPS: NavGroup[] = [
  { items: [{ label: "Dashboard", href: "/institution/dashboard", icon: LayoutDashboard }] },
  {
    label: "Students",
    items: [
      { label: "Students", href: "/institution/students", icon: Users },
      { label: "Departments", href: "/institution/departments", icon: Building2 },
    ],
  },
  {
    label: "Placements",
    items: [
      { label: "Placements", href: "/institution/placements", icon: Trophy },
      { label: "Drives", href: "/institution/placements/drives", icon: CalendarDays },
      { label: "Outcomes", href: "/institution/placements/outcomes", icon: FileText },
    ],
  },
  {
    label: "Analytics",
    items: [
      { label: "Overview", href: "/institution/analytics", icon: BarChart3 },
      { label: "Department Analytics", href: "/institution/analytics/departments", icon: BarChart3 },
      { label: "Skill Analytics", href: "/institution/analytics/skills", icon: BarChart3 },
      { label: "Placement Analytics", href: "/institution/analytics/placements", icon: BarChart3 },
      { label: "Skill Gaps", href: "/institution/skill-gaps", icon: TrendingDown },
    ],
  },
  {
    label: "Partnerships",
    items: [
      { label: "Industry Partners", href: "/institution/industry-partners", icon: Handshake },
      { label: "Collaborations", href: "/institution/collaborations", icon: Handshake },
    ],
  },
  {
    label: "Other",
    items: [
      { label: "Assessments", href: "/institution/assessments", icon: ClipboardCheck },
      { label: "Events", href: "/institution/events", icon: CalendarDays },
      { label: "Reports", href: "/institution/reports", icon: FileText },
    ],
  },
  {
    label: "Account",
    items: [
      { label: "Profile", href: "/institution/profile", icon: User },
      { label: "Settings", href: "/institution/settings", icon: Settings },
    ],
  },
];

export function InstitutionSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 shrink-0 items-center gap-2 border-b px-4">
        <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight" onClick={onNavigate}>
          <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-600 text-sm text-white">
            A
          </span>
          AIC Portal
        </Link>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto px-3 py-4">
        {NAV_GROUPS.map((group, i) => (
          <div key={group.label ?? i} className="space-y-1">
            {group.label ? (
              <p className="px-2.5 text-[11px] font-semibold tracking-wider text-muted-foreground uppercase">
                {group.label}
              </p>
            ) : null}
            {group.items.map((item) => {
              const Icon = item.icon;
              const active = item.href && (pathname === item.href || pathname.startsWith(`${item.href}/`));

              return (
                <Link
                  key={item.href}
                  href={item.href!}
                  onClick={onNavigate}
                  className={cn(
                    "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
                      : "text-foreground/70 hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon className="size-4 shrink-0" aria-hidden="true" />
                  {item.label}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
    </div>
  );
}
