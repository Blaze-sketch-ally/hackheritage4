"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BadgeCheck,
  BarChart3,
  BookOpen,
  Briefcase,
  Building2,
  CalendarDays,
  FolderKanban,
  GraduationCap,
  Handshake,
  LayoutDashboard,
  type LucideIcon,
  Network,
  Presentation,
  Settings,
  UserCheck,
  Users,
} from "lucide-react";
import { cn } from "@/lib/utils";

interface NavItem {
  label: string;
  href: string;
  icon: LucideIcon;
}

interface NavGroup {
  label?: string;
  items: NavItem[];
}

// Every href points at a route that already exists under app/industry/
// (scaffold "Coming Soon" pages are fine — Phase 3 only adds the shell
// around them). Mirrors the grouping/visual conventions of
// components/student/student-sidebar.tsx.
const NAV_GROUPS: NavGroup[] = [
  {
    label: "Main",
    items: [
      { label: "Dashboard", href: "/industry/dashboard", icon: LayoutDashboard },
      { label: "Profile", href: "/industry/profile", icon: Building2 },
    ],
  },
  {
    label: "Opportunities",
    items: [
      { label: "Internships", href: "/industry/internships", icon: GraduationCap },
      { label: "Jobs", href: "/industry/jobs", icon: Briefcase },
      { label: "Projects", href: "/industry/projects", icon: FolderKanban },
      { label: "Training", href: "/industry/training", icon: BookOpen },
      { label: "Workshops", href: "/industry/workshops", icon: Presentation },
      { label: "Mentorship", href: "/industry/mentorship", icon: Handshake },
    ],
  },
  {
    label: "Recruitment",
    items: [
      { label: "Applicants", href: "/industry/applicants", icon: Users },
      { label: "Shortlisted", href: "/industry/shortlisted", icon: UserCheck },
      { label: "Interviews", href: "/industry/interviews", icon: CalendarDays },
      { label: "Selected", href: "/industry/selected", icon: BadgeCheck },
    ],
  },
  {
    label: "Collaboration",
    items: [{ label: "Collaborations", href: "/industry/collaborations", icon: Network }],
  },
  {
    label: "Analytics",
    items: [{ label: "Analytics", href: "/industry/analytics", icon: BarChart3 }],
  },
  {
    label: "System",
    items: [{ label: "Settings", href: "/industry/settings", icon: Settings }],
  },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function IndustrySidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();

  return (
    <div className="flex h-full flex-col">
      <div className="flex h-14 shrink-0 flex-col justify-center gap-0.5 border-b px-4">
        <Link
          href="/"
          className="flex items-center gap-2 font-semibold tracking-tight"
          onClick={onNavigate}
        >
          <span className="flex size-7 items-center justify-center rounded-lg bg-indigo-600 text-sm text-white">
            A
          </span>
          AIC Portal
        </Link>
        <p className="pl-9 text-[11px] font-medium tracking-wide text-muted-foreground">
          Industry Portal
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
