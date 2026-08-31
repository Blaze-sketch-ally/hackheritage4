import { Building2 } from "lucide-react";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { Button } from "@/components/ui/button";
import { COMPANY_SIZE_LABELS, type IndustryProfile } from "@/types/industry";

function initials(name: string | null): string {
  const parts = (name ?? "").trim().split(/\s+/).filter(Boolean);
  if (parts.length >= 2) return (parts[0][0] + parts[1][0]).toUpperCase();
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return "";
}

/** Read view of the company identity block. Mirrors the Student
 * ProfileHeader visually (rounded card, ring, indigo completion meter),
 * but the information architecture is company-specific. */
export function CompanyProfileHeader({
  profile,
  completion,
  onEdit,
}: {
  profile: IndustryProfile;
  completion: number;
  onEdit: () => void;
}) {
  const name = profile.company_name?.trim() || "Your company";
  const secondary = [
    profile.industry_sector,
    profile.headquarters_location,
    profile.company_size ? COMPANY_SIZE_LABELS[profile.company_size] : null,
  ]
    .filter(Boolean)
    .join("  ·  ");

  return (
    <div className="flex flex-col gap-4 rounded-xl bg-card p-6 ring-1 ring-foreground/10 sm:flex-row sm:items-center">
      <Avatar className="size-16 rounded-xl">
        <AvatarImage src={profile.logo_url ?? undefined} alt={name} className="rounded-xl object-contain" />
        <AvatarFallback className="rounded-xl text-lg">
          {initials(profile.company_name) || <Building2 className="size-7" aria-hidden="true" />}
        </AvatarFallback>
      </Avatar>

      <div className="min-w-0 flex-1 space-y-1 text-center sm:text-left">
        <h1 className="truncate text-lg font-semibold">{name}</h1>
        <p className="text-sm text-muted-foreground">
          {secondary || "Company profile is incomplete."}
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
          {profile.created_at ? "Edit Profile" : "Add company details"}
        </Button>
      </div>
    </div>
  );
}
