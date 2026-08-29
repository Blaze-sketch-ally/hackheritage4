"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { Bell, ChevronDown, LogOut, Menu, Search, Settings, User as UserIcon } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Input } from "@/components/ui/input";
import { createClient } from "@/lib/supabase/client";
import { ROLE_LABELS, type PublicRole } from "@/lib/constants";
import type { Profile } from "@/types/user";

function initials(name: string | null, email: string) {
  const source = name?.trim() || email;
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

export function StudentHeader({ profile, onMenuClick }: { profile: Profile; onMenuClick: () => void }) {
  const router = useRouter();
  const displayName = profile.full_name || profile.username || "Student";
  const roleLabel = profile.role && profile.role in ROLE_LABELS
    ? ROLE_LABELS[profile.role as PublicRole].title
    : "Student";

  async function handleSignOut() {
    await createClient().auth.signOut();
    router.push("/login");
    router.refresh();
  }

  return (
    <header className="sticky top-0 z-30 flex h-14 shrink-0 items-center gap-3 border-b bg-card/80 px-4 backdrop-blur supports-backdrop-filter:bg-card/60 sm:px-6">
      <Button variant="ghost" size="icon" className="lg:hidden" onClick={onMenuClick} aria-label="Open menu">
        <Menu />
      </Button>

      <div className="relative hidden max-w-sm flex-1 sm:block">
        <Search
          className="pointer-events-none absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground"
          aria-hidden="true"
        />
        <Input
          placeholder="Search internships, jobs, courses..."
          className="h-9 pl-8"
          disabled
          aria-label="Search (coming soon)"
        />
      </div>

      <div className="flex flex-1 items-center justify-end gap-1.5 sm:flex-none">
        <Button variant="ghost" size="icon" aria-label="Notifications" className="relative" disabled>
          <Bell />
          <span className="absolute top-1.5 right-1.5 size-1.5 rounded-full bg-indigo-500" aria-hidden="true" />
        </Button>

        <DropdownMenu>
          <DropdownMenuTrigger className="flex items-center gap-2 rounded-lg py-1 pr-1.5 pl-1 hover:bg-muted focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50">
            <Avatar size="sm">
              <AvatarImage src={profile.avatar_url ?? undefined} alt={displayName} />
              <AvatarFallback>{initials(profile.full_name, profile.email)}</AvatarFallback>
            </Avatar>
            <span className="hidden flex-col items-start sm:flex">
              <span className="text-xs leading-tight font-medium">{displayName}</span>
              <span className="text-[11px] leading-tight text-muted-foreground">{roleLabel}</span>
            </span>
            <ChevronDown className="hidden size-3.5 text-muted-foreground sm:block" aria-hidden="true" />
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end">
            <div className="px-1.5 py-1">
              <p className="text-sm font-medium">{displayName}</p>
              <p className="text-xs text-muted-foreground">{profile.email}</p>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem render={<Link href="/student/profile" />}>
              <UserIcon /> Profile
            </DropdownMenuItem>
            <DropdownMenuItem render={<Link href="/student/settings" />}>
              <Settings /> Settings
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem variant="destructive" onClick={handleSignOut}>
              <LogOut /> Sign out
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
