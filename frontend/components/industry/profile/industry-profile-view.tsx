"use client";

import { useEffect, useState } from "react";
import { AlertCircle, ExternalLink, RefreshCw } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { FormSuccess } from "@/components/auth/form-success";
import { ApiError } from "@/lib/api";
import { getIndustryProfile } from "@/lib/industry/profile";
import {
  COMPANY_SIZE_LABELS,
  getIndustryProfileCompletion,
  type IndustryProfile,
} from "@/types/industry";
import { CompanyProfileHeader } from "@/components/industry/profile/company-profile-header";
import { IndustryProfileForm } from "@/components/industry/profile/industry-profile-form";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; profile: IndustryProfile };

function fieldsOf(profile: IndustryProfile) {
  return {
    company_name: profile.company_name,
    industry_sector: profile.industry_sector,
    company_size: profile.company_size,
    website_url: profile.website_url,
    company_description: profile.company_description,
    headquarters_location: profile.headquarters_location,
    founded_year: profile.founded_year,
    contact_phone: profile.contact_phone,
    linkedin_url: profile.linkedin_url,
    logo_url: profile.logo_url,
  };
}

/** GET /api/v1/industry/profile, then a read view with an "Edit Profile"
 * action that swaps in IndustryProfileForm (PUT). The backend is the only
 * writer; nothing here derives or caches profile data. */
export function IndustryProfileView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [editing, setEditing] = useState(false);
  const [savedNotice, setSavedNotice] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const profile = await getIndustryProfile();
        if (cancelled) return;
        setState({ status: "ready", profile });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error:
            err instanceof ApiError
              ? err
              : new ApiError(0, "Could not load your company profile."),
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
        <h1 className="text-xl font-semibold">Company Profile</h1>
        <p className="text-sm text-muted-foreground">
          How your company appears to students and institutions across the portal.
        </p>
      </div>

      {state.status === "loading" ? (
        <Card>
          <CardContent
            className="flex items-center justify-center py-10 text-sm text-muted-foreground"
            aria-busy="true"
          >
            Loading your company profile…
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
                  : "Could not load your company profile."}
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
          <IndustryProfileForm
            profile={state.profile}
            onCancel={() => setEditing(false)}
            onSaved={(updated) => {
              setState({ status: "ready", profile: updated });
              setEditing(false);
              setSavedNotice("Company profile saved.");
            }}
          />
        ) : (
          <div className="space-y-6">
            {savedNotice ? <FormSuccess message={savedNotice} /> : null}

            <CompanyProfileHeader
              profile={state.profile}
              completion={getIndustryProfileCompletion(fieldsOf(state.profile))}
              onEdit={() => {
                setSavedNotice(null);
                setEditing(true);
              }}
            />

            <ReadCards profile={state.profile} />
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

function ExternalLinkValue({ href }: { href: string | null }) {
  if (!href) return null;
  return (
    <a
      href={href}
      target="_blank"
      rel="noopener noreferrer"
      className="inline-flex items-center gap-1 text-indigo-600 hover:underline dark:text-indigo-400"
    >
      <span className="max-w-[16rem] truncate">{href}</span>
      <ExternalLink className="size-3.5 shrink-0" aria-hidden="true" />
    </a>
  );
}

function ReadCards({ profile }: { profile: IndustryProfile }) {
  return (
    <>
      <Card>
        <CardHeader>
          <CardTitle>About Company</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2">
            <Row label="Company Name">{profile.company_name}</Row>
            <Row label="Industry Sector">{profile.industry_sector}</Row>
            <Row label="Company Size">
              {profile.company_size ? COMPANY_SIZE_LABELS[profile.company_size] : null}
            </Row>
            <Row label="Founded Year">{profile.founded_year ?? null}</Row>
            <div className="sm:col-span-2">
              <Row label="Company Description">
                {profile.company_description ? (
                  <p className="whitespace-pre-line">{profile.company_description}</p>
                ) : null}
              </Row>
            </div>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Contact &amp; Presence</CardTitle>
        </CardHeader>
        <CardContent>
          <dl className="grid gap-4 sm:grid-cols-2">
            <Row label="Website">
              {profile.website_url ? <ExternalLinkValue href={profile.website_url} /> : null}
            </Row>
            <Row label="LinkedIn">
              {profile.linkedin_url ? <ExternalLinkValue href={profile.linkedin_url} /> : null}
            </Row>
            <Row label="Phone">{profile.contact_phone}</Row>
            <Row label="Headquarters">{profile.headquarters_location}</Row>
          </dl>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Company Branding</CardTitle>
        </CardHeader>
        <CardContent className="space-y-4">
          {profile.logo_url ? (
            // eslint-disable-next-line @next/next/no-img-element
            <img
              src={profile.logo_url}
              alt={`${profile.company_name ?? "Company"} logo`}
              className="size-20 rounded-lg object-contain ring-1 ring-foreground/10"
            />
          ) : (
            <p className="text-sm text-muted-foreground/60">No logo added yet</p>
          )}
          <Row label="Logo URL">
            {profile.logo_url ? <ExternalLinkValue href={profile.logo_url} /> : null}
          </Row>
          <p className="text-xs text-muted-foreground">
            Direct logo upload isn&apos;t available yet — a hosted image URL is used for now.
          </p>
        </CardContent>
      </Card>
    </>
  );
}
