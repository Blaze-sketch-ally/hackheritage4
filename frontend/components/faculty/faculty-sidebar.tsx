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
  LayoutGrid,
  Layers,
  type LucideIcon,
  Presentation,
  Settings,
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

// F3 subphase 1 nav cleanup: an item only carries `href` when the route
// behind it is real (renders actual data/functionality, not a static
// "Coming Soon" page). Items with no href are shown disabled with a
// "Soon" badge instead of linking to a page that isn't real yet --
// same convention already established in StudentSidebar, for the same
// reason (don't let navigation claim a feature exists before it does).
// Question Bank, Assessment Blueprints, Dashboard, Profile, Opportunities
// (F3.2), and Applications (F3.2) are real; every remaining "Engagement"/
// "Other" item is still a static placeholder page as of this phase, so
// it is intentionally NOT linked here even though the page file exists.
// "Applications" reuses the existing industry_collaborations
// recipient-side flow (see faculty-applications-view.tsx) -- "Collaborations"
// below stays Soon rather than becoming a second entry point to the same
// data under a different label.
//
// Phase F5A: the "Assessment" group is renamed "Assessment Studio" and
// gains an "Overview" landing link (assessment-studio-overview.tsx) --
// Question Bank and Blueprints are unchanged, real pages; nothing about
// them moved or was rebuilt, this only gives the group an identifiable
// front door alongside the two existing tools.
const NAV_GROUPS: NavGroup[] = [
  { items: [{ label: "Dashboard", href: "/faculty/dashboard", icon: LayoutDashboard }] },
  {
    label: "Assessment Studio",
    items: [
      { label: "Overview", href: "/faculty/assessment-studio", icon: LayoutGrid },
      { label: "Question Bank", href: "/faculty/questions", icon: Layers },
      { label: "Assessment Blueprints", href: "/faculty/blueprint", icon: FileText },
    ],
  },
  {
    label: "Engagement",
    items: [
      { label: "Research", icon: GraduationCap },
      { label: "Consultancy", icon: Briefcase },
      { label: "FDPs", icon: Presentation },
      { label: "Workshops", icon: CalendarDays },
      { label: "Collaborations", icon: Handshake },
      { label: "Opportunities", href: "/faculty/opportunities", icon: Briefcase },
    ],
  },
  {
    label: "Other",
    items: [
      { label: "Applications", href: "/faculty/applications", icon: FileText },
      { label: "Mentorship", href: "/faculty/mentorship", icon: Users },
      { label: "Calendar", icon: CalendarDays },
      { label: "Internships", icon: BookOpen },
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
