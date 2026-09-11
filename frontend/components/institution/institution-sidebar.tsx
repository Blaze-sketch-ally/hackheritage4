"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SkillBridgeBrand } from "@/components/branding/skillbridge-brand";
import {
  BarChart3,
  Building2,
  CalendarDays,
  Contact,
  FileText,
  GraduationCap,
  Handshake,
  LayoutDashboard,
  type LucideIcon,
  Landmark,
  Network,
  Settings,
  TrendingUp,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
  badge?: string;
}

interface NavGroup {
  label?: string;
  items: NavItem[];
}

// Every href points at a route that already exists under app/institution/
// (all but /institution/collaborations are scaffold "Coming Soon" pages —
// that's fine, this shell only adds navigation + logout around them).
// Mirrors the grouping/visual conventions of
// components/industry/industry-sidebar.tsx.
const NAV_GROUPS: NavGroup[] = [
  {
    label: "Main",
    items: [
      { label: "Dashboard", href: "/institution/dashboard", icon: LayoutDashboard },
      { label: "Profile", href: "/institution/profile", icon: Landmark },
    ],
  },
  {
    label: "Academics",
    items: [
      { label: "Departments", href: "/institution/departments", icon: Building2 },
      { label: "Students", href: "/institution/students", icon: Users },
      { label: "Skill Gaps", href: "/institution/skill-gaps", icon: TrendingUp },
    ],
  },
  {
    label: "Placements",
    items: [
      { label: "Placements", href: "/institution/placements", icon: GraduationCap },
      { label: "Internships", href: "/institution/internships", icon: GraduationCap },
      { label: "Industry Partners", href: "/institution/industry-partners", icon: Handshake },
      { label: "Industry Connections", href: "/institution/industry-connections", icon: Contact },
    ],
  },
  {
    label: "Engagement",
    items: [
      { label: "Collaborations", href: "/institution/collaborations", icon: Network },
      { label: "Events", href: "/institution/events", icon: CalendarDays, badge: "Soon" },
    ],
  },
  {
    label: "Insights",
    items: [
      { label: "Analytics", href: "/institution/analytics", icon: BarChart3 },
      { label: "Reports", href: "/institution/reports", icon: FileText, badge: "Soon" },
    ],
  },
  {
    label: "System",
    items: [{ label: "Settings", href: "/institution/settings", icon: Settings }],
  },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function InstitutionSidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 shrink-0 flex-col justify-center gap-0.5 border-b px-4">
        <Link
          href="/"
          aria-label="SkillBridge home"
          className="flex items-center gap-2 font-semibold tracking-tight"
          onClick={onNavigate}
        >
          <SkillBridgeBrand emblemSize={28} />
        </Link>
        <p className="pl-9 text-[11px] font-medium tracking-wide text-muted-foreground">
          Institution Portal
        </p>
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
              const active = isActive(pathname, item.href);

              return (
                <Link
                  key={item.href}
                  href={item.href}
                  onClick={onNavigate}
                  aria-current={active ? "page" : undefined}
                  className={cn(
                    "flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm font-medium transition-colors",
                    active
                      ? "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400"
                      : "text-foreground/70 hover:bg-muted hover:text-foreground",
                  )}
                >
                  <Icon className="size-4 shrink-0" aria-hidden="true" />
                  <span className="flex-1 truncate">{item.label}</span>
                  {item.badge ? (
                    <span className="rounded-full bg-muted/80 px-1.5 py-0.5 text-[10px] font-medium text-muted-foreground">
                      {item.badge}
                    </span>
                  ) : null}
                </Link>
              );
            })}
          </div>
        ))}
      </nav>
    </div>
  );
}
