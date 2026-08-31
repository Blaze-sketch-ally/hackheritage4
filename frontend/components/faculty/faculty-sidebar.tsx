"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  Briefcase,
  CalendarDays,
  FileText,
  GraduationCap,
  Handshake,
  LayoutDashboard,
  Layers,
  type LucideIcon,
  Presentation,
  Settings,
  User,
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

// Every href below points at a route that already exists in app/faculty/
// (some are scaffold placeholder pages -- see docs/PROJECT_CONTEXT.md §2 --
// but a real route, so they're linked, matching the convention already
// established in StudentSidebar rather than disabled).
const NAV_GROUPS: NavGroup[] = [
  { items: [{ label: "Dashboard", href: "/faculty/dashboard", icon: LayoutDashboard }] },
  {
    label: "Assessment",
    items: [
      { label: "Question Bank", href: "/faculty/questions", icon: Layers },
      { label: "Assessment Blueprints", href: "/faculty/blueprint", icon: FileText },
    ],
  },
  {
    label: "Engagement",
    items: [
      { label: "Research", href: "/faculty/research", icon: GraduationCap },
      { label: "Consultancy", href: "/faculty/consultancy", icon: Briefcase },
      { label: "FDPs", href: "/faculty/fdps", icon: Presentation },
      { label: "Workshops", href: "/faculty/workshops", icon: CalendarDays },
      { label: "Collaborations", href: "/faculty/collaborations", icon: Handshake },
      { label: "Opportunities", href: "/faculty/opportunities", icon: Briefcase },
    ],
  },
  {
    label: "Other",
    items: [
      { label: "Applications", href: "/faculty/applications", icon: FileText },
      { label: "Calendar", href: "/faculty/calendar", icon: CalendarDays },
      { label: "Internships", href: "/faculty/internships", icon: BookOpen },
    ],
  },
  {
    label: "Account",
    items: [
      { label: "Profile", href: "/faculty/profile", icon: User },
      { label: "Settings", href: "/faculty/settings", icon: Settings },
    ],
  },
];

export function FacultySidebar({ onNavigate }: { onNavigate?: () => void }) {
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
