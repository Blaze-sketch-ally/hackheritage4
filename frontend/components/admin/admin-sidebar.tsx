"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { SkillBridgeBrand } from "@/components/branding/skillbridge-brand";
import {
  BadgeCheck,
  Building2,
  ClipboardCheck,
  FileText,
  GraduationCap,
  Landmark,
  Layers,
  LayoutDashboard,
  type LucideIcon,
  Settings,
  ShieldCheck,
  Sparkles,
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

const NAV_GROUPS: NavGroup[] = [
  {
    label: "Overview",
    items: [
      { label: "Dashboard", href: "/admin/dashboard", icon: LayoutDashboard },
      { label: "System Reports", href: "/admin/reports", icon: FileText, badge: "Soon" },
    ],
  },
  {
    label: "Governance",
    items: [
      { label: "Faculty Permissions", href: "/admin/faculty", icon: ShieldCheck },
      { label: "Evaluator Assignments", href: "/admin/assessments", icon: ClipboardCheck },
      { label: "Verification Queue", href: "/admin/verification", icon: BadgeCheck, badge: "Soon" },
      { label: "Opportunity Moderation", href: "/admin/opportunities", icon: Sparkles, badge: "Soon" },
    ],
  },
  {
    label: "Registries",
    items: [
      { label: "Student Directory", href: "/admin/students", icon: GraduationCap, badge: "Soon" },
      { label: "Corporate Partners", href: "/admin/companies", icon: Building2, badge: "Soon" },
      { label: "Institutions", href: "/admin/institutions", icon: Landmark, badge: "Soon" },
      { label: "Skill Taxonomy", href: "/admin/skills", icon: Layers, badge: "Soon" },
    ],
  },
  {
    label: "Management",
    items: [
      { label: "User Governance", href: "/admin/users", icon: Users, badge: "Soon" },
      { label: "Platform Settings", href: "/admin/settings", icon: Settings, badge: "Soon" },
    ],
  },
];

function isActive(pathname: string, href: string): boolean {
  return pathname === href || pathname.startsWith(`${href}/`);
}

export function AdminSidebar({ onNavigate }: { onNavigate?: () => void }) {
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
        <span className="text-[11px] font-semibold tracking-wider text-slate-500 uppercase dark:text-slate-400">
          Admin Console
        </span>
      </div>

      <nav className="flex-1 space-y-6 overflow-y-auto p-3" aria-label="Admin Navigation">
        {NAV_GROUPS.map((group, gIdx) => (
          <div key={group.label ?? gIdx} className="space-y-1">
            {group.label ? (
              <p className="px-3 pb-1 text-[11px] font-semibold tracking-wider text-muted-foreground/70 uppercase">
                {group.label}
              </p>
            ) : null}
            <ul className="space-y-0.5">
              {group.items.map((item) => {
                const Icon = item.icon;
                const active = isActive(pathname, item.href);
                return (
                  <li key={item.href}>
                    <Link
                      href={item.href}
                      onClick={onNavigate}
                      className={cn(
                        "flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors",
                        active
                          ? "bg-slate-800 text-white shadow-sm dark:bg-slate-700"
                          : "text-muted-foreground hover:bg-muted hover:text-foreground",
                      )}
                    >
                      <Icon className="size-4 shrink-0" aria-hidden="true" />
                      <span className="flex-1 truncate">{item.label}</span>
                      {item.badge ? (
                        <span
                          className={cn(
                            "rounded-full px-1.5 py-0.5 text-[10px] font-semibold",
                            active
                              ? "bg-white/20 text-white"
                              : "bg-muted text-muted-foreground group-hover:bg-background",
                          )}
                        >
                          {item.badge}
                        </span>
                      ) : null}
                    </Link>
                  </li>
                );
              })}
            </ul>
          </div>
        ))}
      </nav>

      <div className="border-t p-3 text-xs text-muted-foreground">
        <p className="font-medium text-foreground">SkillBridge System Core</p>
        <p className="text-[11px]">Enterprise Governance Engine</p>
      </div>
    </div>
  );
}
