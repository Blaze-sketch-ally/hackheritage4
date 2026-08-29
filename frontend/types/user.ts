import type { UserRole } from "@/lib/constants";

// Mirrors the `profiles` table (database/migrations/001_profiles.sql).
// `role` and `username` are null until the user completes onboarding.
export interface Profile {
  id: string;
  email: string;
  username: string | null;
  role: UserRole | null;
  full_name: string | null;
  avatar_url: string | null;
  created_at: string;
  updated_at: string;
}
