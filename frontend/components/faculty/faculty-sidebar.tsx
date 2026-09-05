"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BookOpen,
  Briefcase,
  CalendarDays,
  ClipboardCheck,
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
import { hasEvaluationWorkspaceAccess, hasQuestionStudioAccess, useFacultyCapabilitiesContext } from "@/lib/faculty/capabilities";

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
// Dashboard, Profile, Opportunities (F3.2), Applications (F3.2), and
// Mentorship are real; every remaining "Engagement"/"Other" item is
// still a static placeholder page as of this phase, so it is
// intentionally NOT linked here even though the page file exists.
// "Applications" reuses the existing industry_collaborations
// recipient-side flow (see faculty-applications-view.tsx) -- "Collaborations"
// below stays Soon rather than becoming a second entry point to the same
// data under a different label.
//
// Phase 1 (Faculty Dashboard Architecture): this is now ONLY the Faculty
// Connect experience -- the general-Faculty workspace every FACULTY user
// gets regardless of capability. Question Studio and Evaluation
// Workspace used to be a single static "Assessment Studio" group here;
// they are now separate, capability-gated groups computed below, never
// shown to a caller who doesn't (yet) hold the relevant capability. This
// directly addresses the deployment-readiness audit's finding that every
// Faculty member saw Question Bank/Blueprint links regardless of
// capability, with unauthorized access only failing later at the
// backend.
const CONNECT_NAV_GROUPS: NavGroup[] = [
  { items: [{ label: "Dashboard", href: "/faculty/dashboard", icon: LayoutDashboard }] },
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

// Visible only when the caller holds assessment_author and/or
// assessment_reviewer (see hasQuestionStudioAccess) -- Question Bank and
// Blueprints are unchanged, real pages; nothing about them moved or was
// rebuilt, only their visibility became capability-aware.
const QUESTION_STUDIO_GROUP: NavGroup = {
  label: "Question Studio",
  items: [
    { label: "Overview", href: "/faculty/assessment-studio", icon: LayoutGrid },
    { label: "Question Bank", href: "/faculty/questions", icon: Layers },
    { label: "Blueprints", href: "/faculty/blueprint", icon: FileText },
  ],
};

// Visible only when the caller holds assessment_evaluator. Phase 1 only
// establishes this nav entry and its placeholder destination -- the real
// evaluator workspace (assigned evaluations, answers, rubrics, finalize)
// is Phase 2. Deliberately a single real link, never a "Soon"-badged
// disabled item: an evaluator-capable Faculty member genuinely has
// somewhere to go today, it just honestly says what isn't built yet.
const EVALUATION_WORKSPACE_GROUP: NavGroup = {
  label: "Evaluation Workspace",
  items: [{ label: "Overview", href: "/faculty/evaluation-workspace", icon: ClipboardCheck }],
};

export function FacultySidebar({ onNavigate }: { onNavigate?: () => void }) {
  const pathname = usePathname();
  const capabilityState = useFacultyCapabilitiesContext();

  // Deferred, not flickered: while capabilities are loading (or failed to
  // load), these two groups are simply absent -- never rendered and then
  // removed, never briefly shown to a caller who turns out to lack the
  // capability. See the audit's own "no flicker" requirement.
  const groups: NavGroup[] = [...CONNECT_NAV_GROUPS];
  if (capabilityState.status === "ready") {
    if (hasQuestionStudioAccess(capabilityState.capabilities)) groups.push(QUESTION_STUDIO_GROUP);
    if (hasEvaluationWorkspaceAccess(capabilityState.capabilities)) groups.push(EVALUATION_WORKSPACE_GROUP);
  }

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
        {groups.map((group, i) => (
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
