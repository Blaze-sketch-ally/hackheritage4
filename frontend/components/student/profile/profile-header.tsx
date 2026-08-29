import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import type { Profile } from "@/types/user";

function initials(name: string | null, email: string) {
  const source = name?.trim() || email;
  const parts = source.split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  return source.slice(0, 2).toUpperCase();
}

export function ProfileHeader({ profile, completion }: { profile: Profile; completion: number }) {
  const displayName = profile.full_name || profile.username || "Student";

  return (
    <div className="flex flex-col items-center gap-4 rounded-xl bg-card p-6 ring-1 ring-foreground/10 sm:flex-row">
      <Avatar className="size-16">
        <AvatarImage src={profile.avatar_url ?? undefined} alt={displayName} />
        <AvatarFallback className="text-lg">{initials(profile.full_name, profile.email)}</AvatarFallback>
      </Avatar>

      <div className="flex-1 space-y-1 text-center sm:text-left">
        <h1 className="text-lg font-semibold">{displayName}</h1>
        <p className="text-sm text-muted-foreground">
          {profile.username ? `@${profile.username}` : profile.email}
        </p>
      </div>

      <div className="flex flex-col items-center gap-1 sm:items-end">
        <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400">{completion}% complete</span>
        <div className="h-1.5 w-32 overflow-hidden rounded-full bg-muted">
          <div className="h-full rounded-full bg-indigo-500 transition-all" style={{ width: `${completion}%` }} />
        </div>
      </div>
    </div>
  );
}
