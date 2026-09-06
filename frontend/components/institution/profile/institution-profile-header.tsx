import { Landmark } from "lucide-react";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import type { InstitutionProfile } from "@/types/institution";

function initials(name: string | null): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return "";
}

/** Read view of the institution identity block. Mirrors
 * CompanyProfileHeader (components/industry/profile/company-profile-header.tsx)
 * visually; information architecture is institution-specific. */
export function InstitutionProfileHeader({
  profile,
  completion,
  onEdit,
}: {
  profile: InstitutionProfile;
  completion: number;
  onEdit: () => void;
}) {
  const name = profile.institution_name?.trim() || "Your institution";
  const secondary = [profile.institution_type, profile.location].filter(Boolean).join("  ·  ");

  return (
    <div className="flex flex-col gap-4 rounded-xl bg-card p-6 ring-1 ring-foreground/10 sm:flex-row sm:items-center">
      <Avatar className="size-16 rounded-xl">
        <AvatarFallback className="rounded-xl text-lg">
          {initials(profile.institution_name) || <Landmark className="size-7" aria-hidden="true" />}
        </AvatarFallback>
      </Avatar>

      <div className="min-w-0 flex-1 space-y-1 text-center sm:text-left">
        <h1 className="truncate text-lg font-semibold">{name}</h1>
        <p className="text-sm text-muted-foreground">
          {secondary || "Institution profile is incomplete."}
        </p>
      </div>

      <div className="flex flex-col items-center gap-2 sm:items-end">
        <div className="flex flex-col items-center gap-1 sm:items-end">
          <span className="text-sm font-semibold text-indigo-600 dark:text-indigo-400">
            {completion}% complete
          </span>
          <div className="h-1.5 w-32 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-indigo-500 transition-all"
              style={{ width: `${completion}%` }}
            />
          </div>
        </div>
        <Button size="sm" variant="outline" onClick={onEdit}>
          {profile.created_at ? "Edit Profile" : "Add institution details"}
        </Button>
      </div>
    </div>
  );
}
