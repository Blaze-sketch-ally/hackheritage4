import type { SupabaseClient } from "@supabase/supabase-js";
import type { Profile } from "@/types/user";

/**
 * Fetches the full `profiles` row for a user. Generic across every role —
 * role-specific data (e.g. student_profiles) lives in its own module.
 */
export async function fetchProfile(
  supabase: SupabaseClient,
  userId: string,
): Promise<Profile | null> {
  const { data } = await supabase.from("profiles").select("*").eq("id", userId).maybeSingle();
  return (data as Profile | null) ?? null;
}

export interface UpdatableProfileFields {
  full_name: string;
  username: string;
  avatar_url: string | null;
}

/** Updates the shared identity fields on `profiles`. RLS restricts this to the caller's own row. */
export async function updateProfile(
  supabase: SupabaseClient,
  userId: string,
  fields: UpdatableProfileFields,
) {
  return supabase.from("profiles").update(fields).eq("id", userId).select("*").single();
}
