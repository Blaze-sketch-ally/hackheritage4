"use client";

import { useEffect, useState } from "react";
import { AlertCircle, ExternalLink, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { getInstitutionProfile } from "@/lib/institution/profile";
import { getInstitutionProfileCompletion, type InstitutionProfile } from "@/types/institution";
import { InstitutionProfileHeader } from "@/components/institution/profile/institution-profile-header";
import { InstitutionProfileForm } from "@/components/institution/profile/institution-profile-form";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; profile: InstitutionProfile };

function fieldsOf(profile: InstitutionProfile) {
  return {
    institution_name: profile.institution_name,
    institution_type: profile.institution_type,
    location: profile.location,
    website_url: profile.website_url,
    contact_phone: profile.contact_phone,
  };
}

/** GET /api/v1/institution/profile, then a read view with an "Edit
 * Profile" action that swaps in InstitutionProfileForm (PUT). Mirrors
 * components/industry/profile/industry-profile-view.tsx exactly. */
export function InstitutionProfileView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState(false);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const profile = await getInstitutionProfile();
        if (cancelled) return;
        setState({ status: "ready", profile });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error:
            err instanceof ApiError
              ? err
              : new ApiError(0, "Could not load your institution profile."),
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Institution Profile</h1>
        <p className="text-sm text-muted-foreground">
          How your institution appears to students, faculty and industry partners across the
          portal.
        </p>
      </div>

      {state.status === "loading" ? (
        <Card>
          <CardContent
            className="flex items-center justify-center py-10 text-sm text-muted-foreground"
            aria-busy="true"
          >
            Loading your institution profile…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {state.error.status === 401
                  ? "Your session has expired. Please sign in again."
                  : "Could not load your institution profile."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status !== 401 ? (
              <Button
                variant="outline"
                size="sm"
                onClick={() => {
                  setState({ status: "loading" });
                  setReloadKey((k) => k + 1);
                }}
              >
                <RefreshCw className="size-3.5" /> Try again
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? (
        editing ? (
          <InstitutionProfileForm
            profile={state.profile}
            onCancel={() => setEditing(false)}
            onSaved={(updated) => {
              setState({ status: "ready", profile: updated });
              setEditing(false);
              setSavedNotice("Institution profile saved.");
            }}
          />
        ) : (
          <div className="space-y-6">
            {savedNotice ? <FormSuccess message={savedNotice} /> : null}

            <InstitutionProfileHeader
              profile={state.profile}
              completion={getInstitutionProfileCompletion(fieldsOf(state.profile))}
              onEdit={() => {
                setSavedNotice(null);
                setEditing(true);
              }}
            />

            <ReadCard profile={state.profile} />
          </div>
        )
      ) : null}
    </div>
  );
}

function Row({ label, children }: { label: string; children: React.ReactNode }) {
  const empty = children === null || children === undefined || children === "";
  return (
    <div className="space-y-0.5">
      <dt className="text-xs font-medium tracking-wide text-muted-foreground uppercase">{label}</dt>
      <dd className={empty ? "text-sm text-muted-foreground/60" : "text-sm"}>
        {empty ? "Not added yet" : children}
      </dd>
    </div>
  );
}

function ReadCard({ profile }: { profile: InstitutionProfile }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>About Institution</CardTitle>
      </CardHeader>
      <CardContent>
        <dl className="grid gap-4 sm:grid-cols-2">
          <Row label="Institution Name">{profile.institution_name}</Row>
          <Row label="Institution Type">{profile.institution_type}</Row>
          <Row label="Location">{profile.location}</Row>
          <Row label="Contact Phone">{profile.contact_phone}</Row>
          <div className="sm:col-span-2">
            <Row label="Website">
              {profile.website_url ? (
                <a
                  href={profile.website_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="inline-flex items-center gap-1 text-indigo-600 hover:underline dark:text-indigo-400"
                >
                  <span className="max-w-[16rem] truncate">{profile.website_url}</span>
                  <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
                </a>
              ) : null}
            </Row>
          </div>
        </dl>
      </CardContent>
    </Card>
  );
}
