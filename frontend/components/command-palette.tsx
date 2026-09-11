"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import { useTheme } from "next-themes";
import {
  Award,
  Bell,
  BookOpen,
  Briefcase,
  Building2,
  Calendar,
  Command,
  Compass,
  FileText,
  FolderKanban,
  GraduationCap,
  Handshake,
  Laptop,
  LayoutDashboard,
  LogOut,
  Moon,
  Search,
  Settings,
  Sun,
  Target,
  Trophy,
  User,
  Users,
  X,
  type LucideIcon,
} from "lucide-react";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { createClient } from "@/lib/supabase/client";
import { cn } from "@/lib/utils";

interface CommandItem {
  id: string;
  title: string;
  description?: string;
  category: "Navigation" | "Opportunities" | "Actions" | "Preferences";
  icon: LucideIcon;
  href?: string;
  action?: () => void;
  keywords?: string[];
  role?: string;
}

export function CommandPalette({
  role,
  open,
  onOpenChange,
}: {
  role?: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const router = useRouter();
  const { setTheme } = useTheme();
  const [query, setQuery] = React.useState("");
  const [selectedIndex, setSelectedIndex] = React.useState(0);
  const inputRef = React.useRef<HTMLInputElement>(null);

  const normalizedRole = role?.toUpperCase();

  const handleSignOut = React.useCallback(async () => {
    onOpenChange(false);
    await createClient().auth.signOut();
    router.push("/login");
    router.refresh();
  }, [onOpenChange, router]);

  const items: CommandItem[] = React.useMemo(() => {
    const list: CommandItem[] = [];

    // Common Nav
    if (normalizedRole === "STUDENT") {
      list.push(
        { id: "s-dash", title: "Dashboard", description: "Student overview & KPIs", category: "Navigation", icon: LayoutDashboard, href: "/student/dashboard", keywords: ["home", "main"] },
        { id: "s-profile", title: "Profile", description: "Your skills, portfolio, and bio", category: "Navigation", icon: User, href: "/student/profile", keywords: ["account", "cv"] },
        { id: "s-opps", title: "Opportunities & Internships", description: "Browse open postings", category: "Opportunities", icon: Briefcase, href: "/student/opportunities", keywords: ["jobs", "internships", "apply"] },
        { id: "s-apps", title: "My Applications", description: "Track application statuses", category: "Opportunities", icon: FileText, href: "/student/applications", keywords: ["status", "stage"] },
        { id: "s-skills", title: "Skills & Assessments", description: "Verified skill badges & tests", category: "Navigation", icon: Target, href: "/student/skills", keywords: ["tests", "quizzes", "score"] },
        { id: "s-learn", title: "Learning & Courses", description: "Skill roadmaps & modules", category: "Navigation", icon: BookOpen, href: "/student/learning", keywords: ["study", "course"] },
        { id: "s-port", title: "Portfolio Builder", description: "Showcase projects & credentials", category: "Navigation", icon: Award, href: "/student/portfolio", keywords: ["showcase", "github"] },
        { id: "s-mentor", title: "Mentorship", description: "Find faculty & industry mentors", category: "Navigation", icon: Users, href: "/student/mentorship", keywords: ["guide", "advice"] },
        { id: "s-notif", title: "Notifications", description: "Alerts & stage updates", category: "Navigation", icon: Bell, href: "/student/notifications", keywords: ["alerts", "inbox"] },
        { id: "s-settings", title: "Settings", description: "Preferences & security", category: "Navigation", icon: Settings, href: "/student/settings", keywords: ["password", "config"] }
      );
    } else if (normalizedRole === "FACULTY") {
      list.push(
        { id: "f-dash", title: "Dashboard", description: "Faculty workspace & tasks", category: "Navigation", icon: LayoutDashboard, href: "/faculty/dashboard", keywords: ["home"] },
        { id: "f-profile", title: "Profile", description: "Academic bio & credentials", category: "Navigation", icon: User, href: "/faculty/profile", keywords: ["account"] },
        { id: "f-opps", title: "Industry Opportunities", description: "Research grants & projects", category: "Opportunities", icon: Briefcase, href: "/faculty/opportunities", keywords: ["grants", "funding"] },
        { id: "f-eval", title: "Evaluations & Grading", description: "Review assessments & rubrics", category: "Navigation", icon: Award, href: "/faculty/evaluations", keywords: ["grades", "rubric"] },
        { id: "f-collab", title: "Collaborations", description: "Active industry R&D proposals", category: "Navigation", icon: Handshake, href: "/faculty/collaborations", keywords: ["partner", "r&d"] },
        { id: "f-notif", title: "Notifications", description: "System & collaboration alerts", category: "Navigation", icon: Bell, href: "/faculty/notifications", keywords: ["alerts"] },
        { id: "f-settings", title: "Settings", description: "Preferences & profile settings", category: "Navigation", icon: Settings, href: "/faculty/settings", keywords: ["config"] }
      );
    } else if (normalizedRole === "INDUSTRY") {
      list.push(
        { id: "i-dash", title: "Dashboard", description: "Hiring pipeline & postings", category: "Navigation", icon: LayoutDashboard, href: "/industry/dashboard", keywords: ["home"] },
        { id: "i-profile", title: "Company Profile", description: "Organization details & branding", category: "Navigation", icon: Building2, href: "/industry/profile", keywords: ["company", "branding"] },
        { id: "i-post", title: "Job & Internship Postings", description: "Manage active openings", category: "Opportunities", icon: Briefcase, href: "/industry/postings", keywords: ["jobs", "openings"] },
        { id: "i-app", title: "Candidate Applicants", description: "Review ATS applications", category: "Opportunities", icon: Users, href: "/industry/applicants", keywords: ["candidates", "resumes"] },
        { id: "i-talent", title: "Talent Search", description: "Discover verified student skills", category: "Opportunities", icon: Compass, href: "/industry/talent-search", keywords: ["search", "candidates"] },
        { id: "i-proj", title: "Sponsored Projects", description: "Industry capstones & challenges", category: "Opportunities", icon: FolderKanban, href: "/industry/projects", keywords: ["projects", "challenges"] },
        { id: "i-settings", title: "Settings", description: "Team & hiring preferences", category: "Navigation", icon: Settings, href: "/industry/settings", keywords: ["config"] }
      );
    } else if (normalizedRole === "INSTITUTION") {
      list.push(
        { id: "inst-dash", title: "Dashboard", description: "Institutional metrics & overview", category: "Navigation", icon: LayoutDashboard, href: "/institution/dashboard", keywords: ["home", "overview"] },
        { id: "inst-profile", title: "Institution Profile", description: "Campus details & leadership", category: "Navigation", icon: Building2, href: "/institution/profile", keywords: ["campus", "accreditation"] },
        { id: "inst-dept", title: "Departments", description: "Faculty counts & enrollment", category: "Navigation", icon: Building2, href: "/institution/departments", keywords: ["departments", "faculty"] },
        { id: "inst-stud", title: "Students Census", description: "Cohort & academic metrics", category: "Navigation", icon: Users, href: "/institution/students", keywords: ["students", "cohort"] },
        { id: "inst-place", title: "Placements & Internships", description: "Institutional placement records", category: "Navigation", icon: Trophy, href: "/institution/placements", keywords: ["placement", "recruiting"] },
        { id: "inst-part", title: "Industry Partners", description: "Active MoUs & collaborations", category: "Navigation", icon: Handshake, href: "/institution/industry-partners", keywords: ["partners", "mou"] },
        { id: "inst-settings", title: "Settings", description: "Administrative preferences", category: "Navigation", icon: Settings, href: "/institution/settings", keywords: ["config"] }
      );
    } else if (normalizedRole === "ADMIN") {
      list.push(
        { id: "adm-dash", title: "Admin Dashboard", description: "Platform telemetry & health", category: "Navigation", icon: LayoutDashboard, href: "/admin", keywords: ["admin", "system"] },
        { id: "adm-users", title: "User Management", description: "Accounts, roles, & access", category: "Navigation", icon: Users, href: "/admin/users", keywords: ["roles", "accounts"] },
        { id: "adm-logs", title: "Audit Logs", description: "System activity trail", category: "Navigation", icon: FileText, href: "/admin/audit-logs", keywords: ["security", "logs"] }
      );
    }

    // Theme & Preferences
    list.push(
      {
        id: "theme-light",
        title: "Switch to Light Theme",
        description: "Set interface to clean light mode",
        category: "Preferences",
        icon: Sun,
        action: () => setTheme("light"),
        keywords: ["white", "day"],
      },
      {
        id: "theme-dark",
        title: "Switch to Dark Theme",
        description: "Set interface to high-contrast dark mode",
        category: "Preferences",
        icon: Moon,
        action: () => setTheme("dark"),
        keywords: ["night", "black"],
      },
      {
        id: "theme-system",
        title: "Switch to System Theme",
        description: "Match operating system appearance",
        category: "Preferences",
        icon: Laptop,
        action: () => setTheme("system"),
        keywords: ["auto", "os"],
      }
    );

    // Actions
    list.push({
      id: "act-signout",
      title: "Sign Out",
      description: "End your current session securely",
      category: "Actions",
      icon: LogOut,
      action: handleSignOut,
      keywords: ["logout", "exit"],
    });

    return list;
  }, [normalizedRole, setTheme, handleSignOut]);

  const filteredItems = React.useMemo(() => {
    if (!query.trim()) return items;
    const q = query.toLowerCase().trim();
    return items.filter(
      (item) =>
        item.title.toLowerCase().includes(q) ||
        item.description?.toLowerCase().includes(q) ||
        item.keywords?.some((k) => k.toLowerCase().includes(q))
    );
  }, [items, query]);

  // Reset selectedIndex when filter changes
  React.useEffect(() => {
    setSelectedIndex(0);
  }, [filteredItems.length]);

  const executeItem = React.useCallback(
    (item: CommandItem) => {
      onOpenChange(false);
      setQuery("");
      if (item.action) {
        item.action();
      } else if (item.href) {
        router.push(item.href);
      }
    },
    [onOpenChange, router]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "ArrowDown") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev + 1) % Math.max(1, filteredItems.length));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setSelectedIndex((prev) => (prev - 1 + filteredItems.length) % Math.max(1, filteredItems.length));
    } else if (e.key === "Enter" && filteredItems[selectedIndex]) {
      e.preventDefault();
      executeItem(filteredItems[selectedIndex]);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="overflow-hidden p-0 sm:max-w-xl">
        <DialogHeader className="sr-only">
          <DialogTitle>Command Palette</DialogTitle>
          <DialogDescription>Quickly search routes and actions</DialogDescription>
        </DialogHeader>

        <div className="flex items-center border-b px-3">
          <Search className="size-4 shrink-0 text-muted-foreground" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            onKeyDown={handleKeyDown}
            placeholder="Type a command, page, or search..."
            className="flex h-12 w-full rounded-md bg-transparent px-3 py-3 text-sm outline-none placeholder:text-muted-foreground"
            autoFocus
          />
          {query ? (
            <button
              onClick={() => setQuery("")}
              className="rounded p-1 text-muted-foreground hover:text-foreground"
              aria-label="Clear query"
            >
              <X className="size-3.5" />
            </button>
          ) : (
            <kbd className="pointer-events-none hidden h-5 select-none items-center gap-1 rounded border bg-muted px-1.5 font-mono text-[10px] font-medium text-muted-foreground sm:inline-flex">
              ESC
            </kbd>
          )}
        </div>

        <div className="max-h-80 overflow-y-auto p-2" role="listbox">
          {filteredItems.length === 0 ? (
            <div className="py-8 text-center text-sm text-muted-foreground">
              No matching commands or pages found.
            </div>
          ) : (
            filteredItems.map((item, idx) => {
              const Icon = item.icon;
              const isSelected = idx === selectedIndex;

              return (
                <div
                  key={item.id}
                  role="option"
                  aria-selected={isSelected}
                  onMouseEnter={() => setSelectedIndex(idx)}
                  onClick={() => executeItem(item)}
                  className={cn(
                    "flex cursor-pointer items-center justify-between rounded-lg px-3 py-2.5 text-sm transition-colors",
                    isSelected
                      ? "bg-accent text-accent-foreground"
                      : "text-foreground/80 hover:bg-accent/50"
                  )}
                >
                  <div className="flex items-center gap-3">
                    <div
                      className={cn(
                        "flex size-7 items-center justify-center rounded-md border",
                        isSelected ? "bg-background shadow-xs" : "bg-muted/40"
                      )}
                    >
                      <Icon className="size-3.5" />
                    </div>
                    <div>
                      <p className="font-medium leading-none">{item.title}</p>
                      {item.description ? (
                        <p className="mt-0.5 text-xs text-muted-foreground">
                          {item.description}
                        </p>
                      ) : null}
                    </div>
                  </div>

                  <span className="text-[11px] font-medium text-muted-foreground">
                    {item.category}
                  </span>
                </div>
              );
            })
          )}
        </div>

        <div className="flex items-center justify-between border-t bg-muted/40 px-3 py-2 text-[11px] text-muted-foreground">
          <div className="flex items-center gap-2">
            <span>Navigation:</span>
            <kbd className="rounded border bg-background px-1 py-0.5 font-mono text-[10px]">↑</kbd>
            <kbd className="rounded border bg-background px-1 py-0.5 font-mono text-[10px]">↓</kbd>
            <span className="ml-1">Select:</span>
            <kbd className="rounded border bg-background px-1 py-0.5 font-mono text-[10px]">↵</kbd>
          </div>
          <span className="font-mono text-[10px]">AIC Portal Quick Search</span>
        </div>
      </DialogContent>
    </Dialog>
  );
}

/**
 * Clickable search trigger button for placement in any header.
 * Replaces the static disabled search input with an interactive trigger.
 */
export function CommandPaletteTrigger({
  role,
  placeholder = "Search or type Cmd+K...",
  className,
}: {
  role?: string | null;
  placeholder?: string;
  className?: string;
}) {
  const [open, setOpen] = React.useState(false);

  React.useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === "k") {
        e.preventDefault();
        setOpen((prev) => !prev);
      }
    };

    window.addEventListener("keydown", handleKeyDown);
    return () => window.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <>
      <button
        type="button"
        onClick={() => setOpen(true)}
        aria-label="Open command palette search"
        className={cn(
          "group flex h-9 w-full max-w-sm items-center justify-between rounded-lg border border-input bg-background/80 px-3 text-sm text-muted-foreground transition-all hover:border-ring/50 hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring",
          className
        )}
      >
        <span className="flex items-center gap-2 overflow-hidden text-ellipsis whitespace-nowrap">
          <Search className="size-4 shrink-0 transition-colors group-hover:text-foreground" />
          <span className="text-xs sm:text-sm">{placeholder}</span>
        </span>
        <kbd className="pointer-events-none hidden select-none items-center gap-0.5 rounded border bg-muted px-1.5 font-mono text-[10px] font-semibold text-muted-foreground sm:inline-flex">
          <Command className="size-2.5" />K
        </kbd>
      </button>

      <CommandPalette role={role} open={open} onOpenChange={setOpen} />
    </>
  );
}
