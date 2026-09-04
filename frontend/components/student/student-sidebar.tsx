"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  Award,
  Bell,
  BookOpen,
  Briefcase,
  Building2,
  CalendarDays,
  ClipboardCheck,
  Compass,
  FileText,
  FolderKanban,
  GraduationCap,
  Handshake,
  LayoutDashboard,
  type LucideIcon,
  Settings,
  Sparkles,
  Target,
  Trophy,
  User,
  Users,
  Layers,
  TrendingUp,
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

// Every href below points at a route that already exists in app/student/
// (scaffold placeholder pages are fine — see docs/PROJECT_CONTEXT.md §2).
// Items with no href (e.g. Industry Projects) have no matching route yet
// and are shown as "Soon" rather than linking to a page that isn't theirs.
const NAV_GROUPS: NavGroup[] = [
  { items: [{ label: "Dashboard", href: "/student/dashboard", icon: LayoutDashboard }] },
  {
    label: "Main",
    items: [
      { label: "Skills & Assessment", href: "/student/skills", icon: Target },
      { label: "Assessments", href: "/student/assessment", icon: ClipboardCheck },
      { label: "Skill Gap Analysis", href: "/student/skill-gap", icon: TrendingUp },
      { label: "Recommended For You", href: "/student/recommendations", icon: Sparkles },
      { label: "Career", href: "/student/career", icon: Compass },
      { label: "Learning & Courses", href: "/student/learning", icon: BookOpen },
      { label: "Internships", href: "/student/internships", icon: Briefcase },
      { label: "My Internships", href: "/student/my-internships", icon: GraduationCap },
      { label: "Jobs & Placements", href: "/student/jobs", icon: Building2 },
      { label: "Applications", href: "/student/applications", icon: FileText },
    ],
  },
  {
    label: "Portfolio",
    items: [
      { label: "My Portfolio", href: "/student/portfolio", icon: Layers },
      { label: "Projects", href: "/student/projects", icon: FolderKanban },
      { label: "Certifications", href: "/student/certifications", icon: Award },
      { label: "Achievements", href: "/student/achievements", icon: Trophy },
    ],
  },
  {
    label: "Network",
    items: [
      { label: "Mentorship", href: "/student/mentorship", icon: Users },
      { label: "Events", href: "/student/events", icon: CalendarDays },
      { label: "Industry Projects", icon: Handshake },
    ],
  },
  {
    label: "Account",
    items: [
      { label: "Notifications", href: "/student/notifications", icon: Bell },
      { label: "Profile", href: "/student/profile", icon: User },
      { label: "Settings", href: "/student/settings", icon: Settings },
    ],
  },
];

export function StudentSidebar({ onNavigate }: { onNavigate?: () => void }) {
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

              if (!item.href) {
                return (
                  <div
                    key={item.label}
                    className="flex items-center gap-2.5 rounded-lg px-2.5 py-2 text-sm text-muted-foreground/60"
                  >
                    <Icon className="size-4 shrink-0" aria-hidden="true" />
                    <span className="flex-1">{item.label}</span>
                    <span className="rounded-full bg-muted px-1.5 py-0.5 text-[10px] font-medium">Soon</span>
                  </div>
                );
              }

              const active = pathname === item.href || pathname.startsWith(`${item.href}/`);

              return (
                <Link
                  key={item.href}
                  href={item.href}
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
