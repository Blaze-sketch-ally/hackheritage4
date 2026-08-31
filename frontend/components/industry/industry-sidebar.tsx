"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Briefcase,
  CalendarCheck,
  FolderKanban,
  GraduationCap,
  Handshake,
  LayoutDashboard,
  type LucideIcon,
  Settings,
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

// Every href below points at a route that already exists in app/industry/
// (some are scaffold placeholder pages, linked anyway — matching the
// convention already established in StudentSidebar/FacultySidebar).
const NAV_GROUPS: NavGroup[] = [
  { items: [{ label: "Dashboard", href: "/industry/dashboard", icon: LayoutDashboard }] },
  {
    label: "Hiring",
    items: [
      { label: "Internships", href: "/industry/internships", icon: Briefcase },
      { label: "Jobs", href: "/industry/jobs", icon: Briefcase },
      { label: "Applicants", href: "/industry/applicants", icon: Users },
      { label: "Shortlisted", href: "/industry/shortlisted", icon: Trophy },
      { label: "Interviews", href: "/industry/interviews", icon: CalendarCheck },
    ],
  },
  {
    label: "Engagement",
    items: [
      { label: "Projects", href: "/industry/projects", icon: FolderKanban },
      { label: "Mentorship", href: "/industry/mentorship", icon: GraduationCap },
      { label: "Training", href: "/industry/training", icon: GraduationCap },
      { label: "Workshops", href: "/industry/workshops", icon: CalendarCheck },
      { label: "Collaborations", href: "/industry/collaborations", icon: Handshake },
    ],
  },
  {
    label: "Insights",
    items: [{ label: "Analytics", href: "/industry/analytics", icon: BarChart3 }],
  },
  {
    label: "Account",
    items: [
      { label: "Profile", href: "/industry/profile", icon: User },
      { label: "Settings", href: "/industry/settings", icon: Settings },
    ],
  },
];

export function IndustrySidebar({ onNavigate }: { onNavigate?: () => void }) {
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
