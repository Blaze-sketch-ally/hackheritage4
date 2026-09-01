"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, ExternalLink, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { createClient } from "@/lib/supabase/client";
import { fetchProfile } from "@/lib/profile";
import { IndustryAccountSettingsForm } from "@/components/industry/settings/industry-account-settings-form";
import { ChangePasswordForm } from "@/components/industry/settings/change-password-form";
import type { Profile } from "@/types/user";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; profile: Profile };

/**
 * Page-level wrapper for /industry/settings. The industry layout
 * (app/industry/layout.tsx) already guarantees an authenticated INDUSTRY
 * user reaches this point -- this component only needs to load that
 * user's own `profiles` row, the same direct-Supabase path
 * fetchProfile()/updateProfile() (lib/profile.ts) already use elsewhere
 * (this data never goes through the FastAPI backend, matching the
 * existing auth/profile architecture boundary).
 */
export function IndustrySettingsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const supabase = createClient();
        const {
          data: { user },
        } = await supabase.auth.getUser();

        if (!user) {
          if (!cancelled) {
            setState({
              status: "error",
              message: "Your session has expired. Please sign in again.",
            });
          }
          return;
        }

        const profile = await fetchProfile(supabase, user.id);
        if (cancelled) return;

        if (!profile) {
          setState({ status: "error", message: "Could not load your account." });
          return;
        }

        setState({ status: "ready", profile });
      } catch (err) {
        console.error("Settings load failed:", err);
        if (!cancelled) {
          setState({
            status: "error",
            message: "Could not load your account. Please try again.",
          });
        }
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your own Industry account — name, username, avatar, and password.
        </p>
      </div>

      <div className="flex flex-col gap-3 rounded-lg border px-4 py-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium">Company Profile</p>
          <p className="text-xs text-muted-foreground">
            Company name, industry sector, and other organization details are managed separately.
          </p>
        </div>
        <Button variant="outline" size="sm" className="shrink-0" render={<Link href="/industry/profile" />}>
          Manage Company Profile <ExternalLink className="size-3.5" />
        </Button>
      </div>

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading your account…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">{state.message}</p>
            <Button variant="outline" size="sm" onClick={reload}>
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? (
        <>
          <IndustryAccountSettingsForm
            profile={state.profile}
            onSaved={(updated) => setState({ status: "ready", profile: updated })}
          />
          <ChangePasswordForm />
        </>
      ) : null}
    </div>
  );
}
