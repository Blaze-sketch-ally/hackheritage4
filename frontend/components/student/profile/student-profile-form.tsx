"use client";

import { useId, useState } from "react";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { FieldError } from "@/components/auth/field-error";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { TagInput } from "@/components/student/profile/tag-input";
import { createClient } from "@/lib/supabase/client";
import { getAuthErrorMessage } from "@/lib/auth";
import { updateProfile } from "@/lib/profile";
import {
  getProfileCompletion,
  upsertStudentProfile,
  type StudentProfile,
  type StudentProfileFields,
} from "@/lib/student/profile";
import { GENDER_OPTIONS, type Gender } from "@/lib/constants";
import { isValidFullName, isValidPhone, isValidUrl, isValidUsername } from "@/lib/validations";
import type { Profile } from "@/types/user";

interface FieldErrors {
  fullName?: string;
  username?: string;
  avatarUrl?: string;
  phone?: string;
  dateOfBirth?: string;
  graduationYear?: string;
  cgpa?: string;
  percentage?: string;
}

function todayIsoDate() {
  return new Date().toISOString().slice(0, 10);
}

function toFormState(profile: Profile, studentProfile: StudentProfile | null) {
  return {
    fullName: profile.full_name ?? "",
    username: profile.username ?? "",
    avatarUrl: profile.avatar_url ?? "",
    phone: studentProfile?.phone ?? "",
    dateOfBirth: studentProfile?.date_of_birth ?? "",
    gender: (studentProfile?.gender as Gender | null) ?? null,
    location: studentProfile?.location ?? "",
    institutionName: studentProfile?.institution_name ?? "",
    department: studentProfile?.department ?? "",
    degree: studentProfile?.degree ?? "",
    graduationYear: studentProfile?.graduation_year?.toString() ?? "",
    cgpa: studentProfile?.cgpa?.toString() ?? "",
    percentage: studentProfile?.percentage?.toString() ?? "",
    careerGoals: studentProfile?.career_goals ?? "",
    preferredRoles: studentProfile?.preferred_roles ?? [],
    preferredLocations: studentProfile?.preferred_locations ?? [],
    interests: studentProfile?.interests ?? [],
  };
}

type FormState = ReturnType<typeof toFormState>;

export function StudentProfileForm({
  profile,
  studentProfile,
}: {
  profile: Profile;
  studentProfile: StudentProfile | null;
}) {
  const router = useRouter();
  const initial = toFormState(profile, studentProfile);

  const [form, setForm] = useState<FormState>(initial);
  const [fieldErrors, setFieldErrors] = useState<FieldErrors>({});
  const [formError, setFormError] = useState<string | null>(null);
  const [formSuccess, setFormSuccess] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  const ids = {
    fullName: useId(),
    username: useId(),
    avatarUrl: useId(),
    phone: useId(),
    dateOfBirth: useId(),
    gender: useId(),
    location: useId(),
    institutionName: useId(),
    department: useId(),
    degree: useId(),
    graduationYear: useId(),
    cgpa: useId(),
    percentage: useId(),
    careerGoals: useId(),
  };

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function validate(): boolean {
    const errors: FieldErrors = {};
    const currentYear = new Date().getFullYear();

    if (!form.fullName.trim() || !isValidFullName(form.fullName)) {
      errors.fullName = "Please enter your full name.";
    }
    if (!form.username.trim() || !isValidUsername(form.username)) {
      errors.username = "3-30 characters: letters, numbers, underscore, dot, or dash.";
    }
    if (form.avatarUrl.trim() && !isValidUrl(form.avatarUrl)) {
      errors.avatarUrl = "Please enter a valid URL.";
    }
    if (form.phone.trim() && !isValidPhone(form.phone)) {
      errors.phone = "7-20 characters: digits, spaces, +, -, or parentheses.";
    }
    if (form.dateOfBirth.trim() && form.dateOfBirth > todayIsoDate()) {
      errors.dateOfBirth = "Date of birth can't be in the future.";
    }
    if (form.graduationYear.trim()) {
      const year = Number(form.graduationYear);
      if (!Number.isInteger(year) || year < currentYear - 10 || year > currentYear + 10) {
        errors.graduationYear = `Enter a year between ${currentYear - 10} and ${currentYear + 10}.`;
      }
    }
    if (form.cgpa.trim()) {
      const cgpa = Number(form.cgpa);
      if (Number.isNaN(cgpa) || cgpa < 0 || cgpa > 10) {
        errors.cgpa = "Enter a value between 0 and 10.";
      }
    }
    if (form.percentage.trim()) {
      const percentage = Number(form.percentage);
      if (Number.isNaN(percentage) || percentage < 0 || percentage > 100) {
        errors.percentage = "Enter a value between 0 and 100.";
      }
    }

    setFieldErrors(errors);
    return Object.keys(errors).length === 0;
  }

  function handleCancel() {
    setForm(initial);
    setFieldErrors({});
    setFormError(null);
    setFormSuccess(null);
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    setFormError(null);
    setFormSuccess(null);

    if (submitting || !validate()) return;
    setSubmitting(true);

    try {
      const supabase = createClient();

      const { error: profileError } = await updateProfile(supabase, profile.id, {
        full_name: form.fullName.trim(),
        username: form.username.trim(),
        avatar_url: form.avatarUrl.trim() || null,
      });

      if (profileError) {
        setFormError(getAuthErrorMessage(profileError));
        setSubmitting(false);
        return;
      }

      const studentFields: StudentProfileFields = {
        phone: form.phone.trim() || null,
        date_of_birth: form.dateOfBirth.trim() || null,
        gender: form.gender,
        location: form.location.trim() || null,
        institution_name: form.institutionName.trim() || null,
        department: form.department.trim() || null,
        degree: form.degree.trim() || null,
        graduation_year: form.graduationYear.trim() ? Number(form.graduationYear) : null,
        cgpa: form.cgpa.trim() ? Number(form.cgpa) : null,
        percentage: form.percentage.trim() ? Number(form.percentage) : null,
        career_goals: form.careerGoals.trim() || null,
        preferred_roles: form.preferredRoles,
        preferred_locations: form.preferredLocations,
        interests: form.interests,
      };

      const { error: studentError } = await upsertStudentProfile(supabase, profile.id, studentFields);

      if (studentError) {
        console.error("student_profiles upsert failed:", studentError.message);
        setFormError(
          "Your basic profile was saved, but we couldn't save the rest of your profile. Please try again.",
        );
        setSubmitting(false);
        return;
      }

      setFormSuccess("Profile updated successfully.");
      router.refresh();
    } catch (err) {
      console.error("Profile update failed:", err);
      setFormError("Unable to save your profile. Please try again.");
    } finally {
      setSubmitting(false);
    }
  }

  const completion = getProfileCompletion(
    { ...profile, full_name: form.fullName, username: form.username, avatar_url: form.avatarUrl || null },
    {
      id: profile.id,
      phone: form.phone || null,
      date_of_birth: form.dateOfBirth || null,
      gender: form.gender,
      location: form.location || null,
      institution_name: form.institutionName || null,
      department: form.department || null,
      degree: form.degree || null,
      graduation_year: form.graduationYear ? Number(form.graduationYear) : null,
      cgpa: form.cgpa ? Number(form.cgpa) : null,
      percentage: form.percentage ? Number(form.percentage) : null,
      career_goals: form.careerGoals || null,
      preferred_roles: form.preferredRoles,
      preferred_locations: form.preferredLocations,
      interests: form.interests,
      created_at: studentProfile?.created_at ?? "",
      updated_at: studentProfile?.updated_at ?? "",
    },
  );

  return (
    <form onSubmit={handleSubmit} noValidate className="space-y-6">
      <FormError message={formError} />
      <FormSuccess message={formSuccess} />

      <Card>
        <CardHeader>
          <CardTitle>Personal Information</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={ids.fullName}>Full Name</Label>
            <Input
              id={ids.fullName}
              value={form.fullName}
              onChange={(e) => set("fullName", e.target.value)}
              disabled={submitting}
              aria-invalid={!!fieldErrors.fullName}
            />
            <FieldError id={`${ids.fullName}-error`} message={fieldErrors.fullName} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.username}>Username</Label>
            <Input
              id={ids.username}
              value={form.username}
              onChange={(e) => set("username", e.target.value)}
              autoCapitalize="none"
              spellCheck={false}
              disabled={submitting}
              aria-invalid={!!fieldErrors.username}
            />
            <FieldError id={`${ids.username}-error`} message={fieldErrors.username} />
          </div>
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor={ids.avatarUrl}>Avatar URL</Label>
            <Input
              id={ids.avatarUrl}
              value={form.avatarUrl}
              onChange={(e) => set("avatarUrl", e.target.value)}
              placeholder="https://..."
              disabled={submitting}
              aria-invalid={!!fieldErrors.avatarUrl}
            />
            <p className="text-xs text-muted-foreground">Paste an image link — file upload is coming later.</p>
            <FieldError id={`${ids.avatarUrl}-error`} message={fieldErrors.avatarUrl} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.phone}>Phone</Label>
            <Input
              id={ids.phone}
              type="tel"
              value={form.phone}
              onChange={(e) => set("phone", e.target.value)}
              placeholder="+91 98765 43210"
              disabled={submitting}
              aria-invalid={!!fieldErrors.phone}
            />
            <FieldError id={`${ids.phone}-error`} message={fieldErrors.phone} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.dateOfBirth}>Date of Birth</Label>
            <Input
              id={ids.dateOfBirth}
              type="date"
              max={todayIsoDate()}
              value={form.dateOfBirth}
              onChange={(e) => set("dateOfBirth", e.target.value)}
              disabled={submitting}
              aria-invalid={!!fieldErrors.dateOfBirth}
            />
            <FieldError id={`${ids.dateOfBirth}-error`} message={fieldErrors.dateOfBirth} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.gender}>Gender</Label>
            <Select
              value={form.gender}
              onValueChange={(value) => set("gender", value as Gender)}
              disabled={submitting}
            >
              <SelectTrigger id={ids.gender} className="w-full">
                <SelectValue placeholder="Select" />
              </SelectTrigger>
              <SelectContent>
                {GENDER_OPTIONS.map((option) => (
                  <SelectItem key={option} value={option}>
                    {option}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.location}>Location</Label>
            <Input
              id={ids.location}
              value={form.location}
              onChange={(e) => set("location", e.target.value)}
              placeholder="e.g. Bengaluru, India"
              disabled={submitting}
            />
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Education</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5">
            <Label htmlFor={ids.institutionName}>College / Institution</Label>
            <Input
              id={ids.institutionName}
              value={form.institutionName}
              onChange={(e) => set("institutionName", e.target.value)}
              disabled={submitting}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.degree}>Degree / Program</Label>
            <Input
              id={ids.degree}
              value={form.degree}
              onChange={(e) => set("degree", e.target.value)}
              placeholder="e.g. B.Tech"
              disabled={submitting}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.department}>Department</Label>
            <Input
              id={ids.department}
              value={form.department}
              onChange={(e) => set("department", e.target.value)}
              placeholder="e.g. Computer Science"
              disabled={submitting}
            />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.graduationYear}>Graduation Year</Label>
            <Input
              id={ids.graduationYear}
              inputMode="numeric"
              value={form.graduationYear}
              onChange={(e) => set("graduationYear", e.target.value)}
              placeholder="e.g. 2027"
              disabled={submitting}
              aria-invalid={!!fieldErrors.graduationYear}
            />
            <FieldError id={`${ids.graduationYear}-error`} message={fieldErrors.graduationYear} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.cgpa}>CGPA</Label>
            <Input
              id={ids.cgpa}
              inputMode="decimal"
              value={form.cgpa}
              onChange={(e) => set("cgpa", e.target.value)}
              placeholder="0.0 - 10.0"
              disabled={submitting}
              aria-invalid={!!fieldErrors.cgpa}
            />
            <FieldError id={`${ids.cgpa}-error`} message={fieldErrors.cgpa} />
          </div>
          <div className="space-y-1.5">
            <Label htmlFor={ids.percentage}>Percentage</Label>
            <Input
              id={ids.percentage}
              inputMode="decimal"
              value={form.percentage}
              onChange={(e) => set("percentage", e.target.value)}
              placeholder="0 - 100"
              disabled={submitting}
              aria-invalid={!!fieldErrors.percentage}
            />
            <FieldError id={`${ids.percentage}-error`} message={fieldErrors.percentage} />
          </div>
          <p className="text-xs text-muted-foreground sm:col-span-2">
            Enter whichever your institution uses — CGPA, percentage, or both.
          </p>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Career</CardTitle>
        </CardHeader>
        <CardContent className="grid gap-4 sm:grid-cols-2">
          <div className="space-y-1.5 sm:col-span-2">
            <Label htmlFor={ids.careerGoals}>Career Goals</Label>
            <textarea
              id={ids.careerGoals}
              value={form.careerGoals}
              onChange={(e) => set("careerGoals", e.target.value)}
              rows={3}
              placeholder="What are you working toward?"
              disabled={submitting}
              className="w-full rounded-lg border border-input bg-transparent px-2.5 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-50 dark:bg-input/30"
            />
          </div>
          <TagInput
            label="Preferred Roles"
            values={form.preferredRoles}
            onChange={(v) => set("preferredRoles", v)}
            placeholder="e.g. Backend Developer"
            disabled={submitting}
          />
          <TagInput
            label="Preferred Locations"
            values={form.preferredLocations}
            onChange={(v) => set("preferredLocations", v)}
            placeholder="e.g. Bengaluru, Remote"
            disabled={submitting}
          />
          <TagInput
            label="Interests"
            values={form.interests}
            onChange={(v) => set("interests", v)}
            placeholder="e.g. Machine Learning"
            disabled={submitting}
          />
        </CardContent>
      </Card>

      <div className="flex flex-col-reverse items-center justify-between gap-3 sm:flex-row">
        <p className="text-sm text-muted-foreground">Profile completion: {completion}%</p>
        <div className="flex w-full gap-3 sm:w-auto">
          <Button
            type="button"
            variant="outline"
            className="flex-1 sm:flex-none"
            onClick={handleCancel}
            disabled={submitting}
          >
            Cancel
          </Button>
          <Button type="submit" className="flex-1 sm:flex-none" disabled={submitting}>
            {submitting ? "Saving..." : "Save Changes"}
          </Button>
        </div>
      </div>
    </form>
  );
}
