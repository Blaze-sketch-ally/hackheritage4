"use client";

import { useId, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { Building2, GraduationCap, Landmark, Users, type LucideIcon } from "lucide-react";
import { Button } from "@/components/ui/button";
import { FormError } from "@/components/auth/form-error";
import { createClient } from "@/lib/supabase/client";
import { getPostLoginRedirectPath, updateProfileRole } from "@/lib/auth";
import { PUBLIC_ROLES, ROLE_LABELS, type PublicRole } from "@/lib/constants";
import { cn } from "@/lib/utils";

const ROLE_ICONS: Record<PublicRole, LucideIcon> = {
  STUDENT: GraduationCap,
  FACULTY: Users,
  INDUSTRY: Building2,
  INSTITUTION: Landmark,
};

interface RoleSelectionProps {
  userId: string;
}

export function RoleSelection({ userId }: RoleSelectionProps) {
  const router = useRouter();
  const groupLabelId = useId();
  const cardRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const [selectedRole, setSelectedRole] = useState<PublicRole | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [signingOut, setSigningOut] = useState(false);
  const [formError, setFormError] = useState<string | null>(null);

  function focusRole(index: number) {
    const wrapped = (index + PUBLIC_ROLES.length) % PUBLIC_ROLES.length;
    setSelectedRole(PUBLIC_ROLES[wrapped]);
    cardRefs.current[wrapped]?.focus();
  }

  function handleKeyDown(index: number, e: React.KeyboardEvent<HTMLButtonElement>) {
    if (e.key === "ArrowRight" || e.key === "ArrowDown") {
      e.preventDefault();
      focusRole(index + 1);
    } else if (e.key === "ArrowLeft" || e.key === "ArrowUp") {
      e.preventDefault();
      focusRole(index - 1);
    }
  }

  async function handleContinue() {
    if (!selectedRole || submitting) return;
    setFormError(null);
    setSubmitting(true);

    try {
      const supabase = createClient();
      const { error } = await updateProfileRole(supabase, userId, selectedRole);

      if (error) {
        console.error("Role update failed:", error.message);
        setFormError("Something went wrong while setting up your account. Please try again.");
        setSubmitting(false);
        return;
      }

      router.push(getPostLoginRedirectPath(selectedRole));
      router.refresh();
    } catch (err) {
      console.error("Role update failed:", err);
      setFormError("Something went wrong while setting up your account. Please try again.");
      setSubmitting(false);
    }
  }

  async function handleSignOut() {
    if (signingOut) return;
    setSigningOut(true);
    try {
      await createClient().auth.signOut();
    } catch (err) {
      console.error("Sign-out failed:", err);
    }
    router.push("/login");
  }

  return (
    <div className="space-y-6">
      <FormError message={formError} />

      <div
        role="radiogroup"
        aria-labelledby={groupLabelId}
        className="grid grid-cols-1 gap-3 sm:grid-cols-2"
      >
        <span id={groupLabelId} className="sr-only">
          What best describes you?
        </span>
        {PUBLIC_ROLES.map((role, index) => {
          const Icon = ROLE_ICONS[role];
          const { title, description } = ROLE_LABELS[role];
          const isSelected = selectedRole === role;

          return (
            <button
              key={role}
              ref={(el) => {
                cardRefs.current[index] = el;
              }}
              type="button"
              role="radio"
              aria-checked={isSelected}
              tabIndex={isSelected || (!selectedRole && index === 0) ? 0 : -1}
              onClick={() => setSelectedRole(role)}
              onKeyDown={(e) => handleKeyDown(index, e)}
              disabled={submitting}
              className={cn(
                "flex flex-col items-start gap-2 rounded-xl border p-4 text-left transition-colors",
                "focus-visible:outline-none focus-visible:ring-3 focus-visible:ring-ring/50",
                isSelected
                  ? "border-primary bg-primary/5 ring-1 ring-primary"
                  : "border-border hover:bg-muted/50",
                submitting && "opacity-50",
              )}
            >
              <Icon
                className={cn("size-6", isSelected ? "text-primary" : "text-muted-foreground")}
                aria-hidden="true"
              />
              <span className="text-sm font-medium">{title}</span>
              <span className="text-xs text-muted-foreground">{description}</span>
            </button>
          );
        })}
      </div>

      <Button
        type="button"
        className="h-10 w-full"
        disabled={!selectedRole || submitting}
        onClick={handleContinue}
      >
        {submitting ? "Setting up your account..." : "Continue"}
      </Button>

      <p className="text-center text-sm text-muted-foreground">
        Not you?{" "}
        <button
          type="button"
          onClick={handleSignOut}
          disabled={signingOut || submitting}
          className="font-medium text-primary underline-offset-4 hover:underline disabled:opacity-50"
        >
          {signingOut ? "Signing out..." : "Sign out"}
        </button>
      </p>
    </div>
  );
}
