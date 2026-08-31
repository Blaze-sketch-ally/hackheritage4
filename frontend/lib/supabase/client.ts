import { createBrowserClient } from "@supabase/ssr";
import type { SupabaseClient } from "@supabase/supabase-js";

// Singleton, not a fresh client per call. Previously this created a brand
// new GoTrueClient instance on every single call -- harmless for a lone
// call, but multiple instances backed by the same localStorage session
// key can contend for the SDK's internal session-refresh lock. Confirmed
// live (Phase 1L+ dashboard work): a component issuing just two
// sequential Supabase-authenticated fetches in short succession (e.g.
// two lib/api.ts calls, each internally calling this function) could
// deadlock on the 3rd/4th client instantiation, permanently hanging
// getSession() and leaving the UI stuck in its loading state -- not a
// network failure, so it never surfaced as a caught error either.
// A singleton (Supabase's own recommended pattern for browser/SPA use)
// removes the multiple-instances-same-storage-key scenario entirely.
let client: SupabaseClient | undefined;

export function createClient() {
  client ??= createBrowserClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
  );
  return client;
}
