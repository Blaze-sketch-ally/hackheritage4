"use client";

import { useId, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { BadgeCheck, ExternalLink, Info, LogOut } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { PasswordInput } from "@/components/auth/password-input";
import { PasswordStrength } from "@/components/auth/password-strength";
import { TagInput } from "@/components/student/profile/tag-input";
import { createClient } from "@/lib/supabase/client";
import { getAuthErrorMessage, updatePassword } from "@/lib/auth";
import { updateProfile } from "@/lib/profile";
import { studentProfileToFields, upsertStudentProfile, type StudentProfile } from "@/lib/student/profile";
import { isPasswordValid } from "@/lib/validations";
import { isValidUsername } from "@/lib/validations";
import type { Profile } from "@/types/user";

export function SettingsView({
  profile,
  studentProfile,
  email,
  emailVerified,
}: {
  profile: Profile;
  studentProfile: StudentProfile | null;
  email: string | null;
  emailVerified: boolean;
}) {
  return (
    <div className="mx-auto flex max-w-3xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">Settings</h1>
        <p className="text-sm text-muted-foreground">
          Manage your account, sign-in, and career preferences.
        </p>
      </div>

      <AccountSection profile={profile} email={email} emailVerified={emailVerified} />
      <PasswordSection />
      <CareerPreferencesSection profile={profile} studentProfile={studentProfile} />
      <ComingSoonSection />
      <AccountActions />
    </div>
  );
}

// ---- Account ----

function AccountSection({
  profile,
  email,
  emailVerified,
}: {
  profile: Profile;
  email: string | null;
  emailVerified: boolean;
}) {
  const router = useRouter();
  const usernameId = useId();
  const [username, setUsername] = useState(profile.username ?? "");
  const [error, setError] = useState<string | null>(null);
  const [fieldError, setFieldError] = useState<string | undefined>();
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  const dirty = username.trim() !== (profile.username ?? "");

  async function save() {
    setError(null);
    setSuccess(null);
    if (!isValidUsername(username)) {
      setFieldError("3–30 characters: letters, numbers, underscore, dot, or dash.");
      return;
    }
    setFieldError(undefined);
    setSaving(true);
    try {
      const { error: err } = await updateProfile(createClient(), profile.id, {
        // full_name / avatar_url are preserved as-is; only username changes here.
        full_name: profile.full_name ?? "",
        username: username.trim(),
        avatar_url: profile.avatar_url,
      });
      if (err) {
        setError(
          err.message?.toLowerCase().includes("duplicate") ||
            err.message?.toLowerCase().includes("unique")
            ? "That username is already taken."
            : getAuthErrorMessage(err),
        );
        return;
      }
      setSuccess("Username updated.");
      router.refresh();
    } catch (err) {
      setError(getAuthErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Account</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <div className="space-y-1.5">
          <Label>Email</Label>
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm">{email ?? "—"}</p>
            {emailVerified ? (
              <Badge variant="default" className="gap-1">
                <BadgeCheck className="size-3" aria-hidden="true" /> Verified
              </Badge>
            ) : (
              <Badge variant="outline">Not verified</Badge>
            )}
          </div>
          <p className="text-xs text-muted-foreground">
            Your email address is managed by your sign-in provider and can&apos;t be changed here.
          </p>
        </div>

        <div className="space-y-1.5">
          <Label>Role</Label>
          <div>
            <Badge variant="secondary">Student</Badge>
          </div>
          <p className="text-xs text-muted-foreground">
            Your role is fixed once set and can&apos;t be changed.
          </p>
        </div>

        <FormError message={error} />
        <FormSuccess message={success} />

        <div className="space-y-1.5">
          <Label htmlFor={usernameId}>Username</Label>
          <div className="flex flex-col gap-2 sm:flex-row">
            <Input
              id={usernameId}
              value={username}
              onChange={(e) => setUsername(e.target.value)}
              autoCapitalize="none"
              spellCheck={false}
              disabled={saving}
              aria-invalid={!!fieldError}
              className="sm:max-w-xs"
            />
            <Button onClick={save} disabled={saving || !dirty}>
              {saving ? "Saving..." : "Save"}
            </Button>
          </div>
          <FieldError id={`${usernameId}-error`} message={fieldError} />
        </div>

        <Button
          variant="ghost"
          size="sm"
          className="w-fit px-0 text-muted-foreground"
          render={<Link href="/student/profile" />}
          nativeButton={false}
        >
          Edit your full profile (name, education, contact) <ExternalLink className="size-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}

// ---- Password ----

function PasswordSection() {
  const newId = useId();
  const confirmId = useId();
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [newError, setNewError] = useState<string | undefined>();
  const [confirmError, setConfirmError] = useState<string | undefined>();
  const [formError, setFormError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setSuccess(null);
    let bad = false;
    if (!isPasswordValid(newPassword)) {
      setNewError("Password does not meet the requirements below.");
      bad = true;
    } else {
      setNewError(undefined);
    }
    if (confirmPassword !== newPassword) {
      setConfirmError("Passwords do not match.");
      bad = true;
    } else {
      setConfirmError(undefined);
    }
    if (bad || saving) return;
    setSaving(true);
    try {
      const { error } = await updatePassword(createClient(), newPassword);
      if (error) {
        setFormError(getAuthErrorMessage(error));
        return;
      }
      setSuccess("Password updated.");
      setNewPassword("");
      setConfirmPassword("");
    } catch (err) {
      setFormError(getAuthErrorMessage(err));
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Password</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} noValidate className="space-y-4">
          <FormError message={formError} />
          <FormSuccess message={success} />
          <div className="space-y-1.5">
            <Label htmlFor={newId}>New password</Label>
            <PasswordInput
              id={newId}
              autoComplete="new-password"
              value={newPassword}
              onChange={(e) => setNewPassword(e.target.value)}
              aria-invalid={!!newError}
              disabled={saving}
              className="sm:max-w-sm"
            />
            <FieldError id={`${newId}-error`} message={newError} />
            {newPassword && <PasswordStrength password={newPassword} />}
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={confirmId}>Confirm new password</Label>
            <PasswordInput
              id={confirmId}
              autoComplete="new-password"
              value={confirmPassword}
              onChange={(e) => setConfirmPassword(e.target.value)}
              aria-invalid={!!confirmError}
              disabled={saving}
              className="sm:max-w-sm"
            />
            <FieldError id={`${confirmId}-error`} message={confirmError} />
          </div>
          <Button
            type="submit"
            disabled={saving || !isPasswordValid(newPassword) || confirmPassword !== newPassword}
          >
            {saving ? "Updating..." : "Update password"}
          </Button>
          <p className="text-xs text-muted-foreground">
            Prefer an email link?{" "}
            <Link href="/forgot-password" className="underline">
              Reset your password by email
            </Link>
            .
          </p>
        </form>
      </CardContent>
    </Card>
  );
}

// ---- Career preferences ----

function CareerPreferencesSection({
  profile,
  studentProfile,
}: {
  profile: Profile;
  studentProfile: StudentProfile | null;
}) {
  const router = useRouter();
  const goalsId = useId();
  const [careerGoals, setCareerGoals] = useState(studentProfile?.career_goals ?? "");
  const [preferredRoles, setPreferredRoles] = useState<string[]>(
    studentProfile?.preferred_roles ?? [],
  );
  const [preferredLocations, setPreferredLocations] = useState<string[]>(
    studentProfile?.preferred_locations ?? [],
  );
  const [interests, setInterests] = useState<string[]>(studentProfile?.interests ?? []);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  async function save() {
    setError(null);
    setSuccess(null);
    setSaving(true);
    try {
      const { error: err } = await upsertStudentProfile(createClient(), profile.id, {
        ...studentProfileToFields(studentProfile),
        career_goals: careerGoals.trim() || null,
        preferred_roles: preferredRoles,
        preferred_locations: preferredLocations,
        interests,
      });
      if (err) {
        setError("Could not save your preferences. Please try again.");
        return;
      }
      setSuccess("Career preferences saved.");
      router.refresh();
    } catch {
      setError("Could not save your preferences. Please try again.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Career preferences</CardTitle>
      </CardHeader>
      <CardContent className="space-y-4">
        <FormError message={error} />
        <FormSuccess message={success} />
        <div className="space-y-1.5">
          <Label htmlFor={goalsId}>Career goals</Label>
          <textarea
            id={goalsId}
            value={careerGoals}
            onChange={(e) => setCareerGoals(e.target.value)}
            rows={3}
            maxLength={5000}
            placeholder="What are you working toward?"
            disabled={saving}
            className="w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30"
          />
        </div>
        <div className="grid gap-4 sm:grid-cols-2">
          <TagInput
            label="Preferred roles"
            values={preferredRoles}
            onChange={setPreferredRoles}
            placeholder="e.g. Backend Developer"
            disabled={saving}
          />
          <TagInput
            label="Preferred locations"
            values={preferredLocations}
            onChange={setPreferredLocations}
            placeholder="e.g. Bengaluru, Remote"
            disabled={saving}
          />
          <TagInput
            label="Interests"
            values={interests}
            onChange={setInterests}
            placeholder="e.g. Machine Learning"
            disabled={saving}
          />
        </div>
        <Button onClick={save} disabled={saving}>
          {saving ? "Saving..." : "Save preferences"}
        </Button>
        <p className="text-xs text-muted-foreground">
          Your <Link href="/student/career" className="underline">target job role</Link> and skill
          gap are managed on the Career and Skill Gap pages.
        </p>
      </CardContent>
    </Card>
  );
}

// ---- Coming soon ----

function ComingSoonSection() {
  const items = [
    "Email notification preferences",
    "Theme (light / dark)",
    "Avatar image upload",
    "Delete account",
  ];
  return (
    <Card>
      <CardHeader>
        <CardTitle className="flex items-center gap-2 text-base">
          <Info className="size-4 text-muted-foreground" aria-hidden="true" />
          More settings
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-2">
        {items.map((label) => (
          <div
            key={label}
            className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2 text-sm"
          >
            <span className="text-muted-foreground">{label}</span>
            <Badge variant="outline">Not available yet</Badge>
          </div>
        ))}
      </CardContent>
    </Card>
  );
}

// ---- Account actions ----

function AccountActions() {
  const router = useRouter();
  const [busy, setBusy] = useState(false);

  async function signOut() {
    setBusy(true);
    try {
      await createClient().auth.signOut();
      router.push("/login");
      router.refresh();
    } catch {
      setBusy(false);
    }
  }

  return (
    <Card>
      <CardContent className="flex flex-wrap items-center justify-between gap-3 py-4">
        <div>
          <p className="text-sm font-medium">Sign out</p>
          <p className="text-xs text-muted-foreground">End your session on this device.</p>
        </div>
        <Button variant="destructive" onClick={signOut} disabled={busy}>
          <LogOut className="size-4" /> {busy ? "Signing out..." : "Sign out"}
        </Button>
      </CardContent>
    </Card>
  );
}
