"use client";

import { useEffect, useState } from "react";
import { AlertCircle, CheckCircle2, Loader2, RefreshCw, Save } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Progress } from "@/components/ui/progress";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { getFacultyProfile, updateFacultyProfile } from "@/lib/faculty/profile";
import type { FacultyProfile, FacultyProfileUpdateInput } from "@/types/faculty-profile";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; profile: FacultyProfile };

type FormState = {
  designation: string;
  department: string;
  institution_name: string;
  phone: string;
  bio: string;
  expertise_areas: string;
  years_of_experience: string;
};

function toFormState(profile: FacultyProfile): FormState {
  return {
    designation: profile.designation ?? "",
    department: profile.department ?? "",
    institution_name: profile.institution_name ?? "",
    phone: profile.phone ?? "",
    bio: profile.bio ?? "",
    expertise_areas: profile.expertise_areas.join(", "),
    years_of_experience: profile.years_of_experience?.toString() ?? "",
  };
}

function toUpdateInput(form: FormState): FacultyProfileUpdateInput {
  return {
    designation: form.designation,
    department: form.department,
    institution_name: form.institution_name,
    phone: form.phone,
    bio: form.bio,
    expertise_areas: form.expertise_areas
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean),
    years_of_experience: form.years_of_experience.trim() === "" ? null : Number(form.years_of_experience),
  };
}

export function FacultyProfileView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [form, setForm] = useState<FormState | null>(null);
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);
  const [savedAt, setSavedAt] = useState<number | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const profile = await getFacultyProfile();
        if (cancelled) return;
        setState({ status: "ready", profile });
        setForm(toFormState(profile));
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load your profile.",
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function retry() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function handleSave() {
    if (!form) return;
    setSaving(true);
    setSaveError(null);
    setSavedAt(null);
    try {
      const profile = await updateFacultyProfile(toUpdateInput(form));
      setState({ status: "ready", profile });
      setForm(toFormState(profile));
      setSavedAt(Date.now());
    } catch (err) {
      setSaveError(err instanceof ApiError ? err.message : "Could not save your profile.");
    } finally {
      setSaving(false);
    }
  }

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading your profile…
        </CardContent>
      </Card>
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <p className="font-medium">{state.message}</p>
          <Button size="sm" onClick={retry}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (!form) return null;
  const { profile } = state;

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardContent className="flex flex-col gap-2 py-4">
          <div className="flex items-center justify-between text-sm">
            <span className="font-medium">Profile completeness</span>
            <span className="text-muted-foreground">{Math.round(profile.completeness * 100)}%</span>
          </div>
          <Progress value={profile.completeness * 100} />
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Academic profile</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-4">
          <div className="grid gap-4 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="designation">Designation</Label>
              <Input
                id="designation"
                placeholder="e.g. Associate Professor"
                value={form.designation}
                onChange={(e) => setForm({ ...form, designation: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="department">Department</Label>
              <Input
                id="department"
                placeholder="e.g. Computer Science"
                value={form.department}
                onChange={(e) => setForm({ ...form, department: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="institution_name">Institution</Label>
              <Input
                id="institution_name"
                value={form.institution_name}
                onChange={(e) => setForm({ ...form, institution_name: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="phone">Phone</Label>
              <Input
                id="phone"
                placeholder="e.g. +91 98765 43210"
                value={form.phone}
                onChange={(e) => setForm({ ...form, phone: e.target.value })}
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="years_of_experience">Years of experience</Label>
              <Input
                id="years_of_experience"
                type="number"
                min={0}
                max={60}
                value={form.years_of_experience}
                onChange={(e) => setForm({ ...form, years_of_experience: e.target.value })}
              />
            </div>
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="bio">Professional bio</Label>
            <Textarea
              id="bio"
              rows={4}
              placeholder="A short summary of your academic background and interests."
              value={form.bio}
              onChange={(e) => setForm({ ...form, bio: e.target.value })}
            />
          </div>

          <div className="flex flex-col gap-1.5">
            <Label htmlFor="expertise_areas">Areas of expertise</Label>
            <Input
              id="expertise_areas"
              placeholder="Comma-separated, e.g. Distributed Systems, Databases"
              value={form.expertise_areas}
              onChange={(e) => setForm({ ...form, expertise_areas: e.target.value })}
            />
          </div>

          {saveError && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertCircle className="size-3.5 shrink-0" /> {saveError}
            </p>
          )}
          {savedAt && !saveError && (
            <p className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
              <CheckCircle2 className="size-3.5 shrink-0" /> Profile saved.
            </p>
          )}

          <div>
            <Button onClick={() => void handleSave()} disabled={saving}>
              {saving ? <Loader2 className="size-3.5 animate-spin" /> : <Save className="size-3.5" />}
              Save profile
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
