"use client";

import { Check, X } from "lucide-react";
import { getPasswordRequirements, getPasswordStrength } from "@/lib/validations";
import { cn } from "@/lib/utils";

const STRENGTH_LABELS = ["Very weak", "Weak", "Fair", "Good", "Strong"];
const STRENGTH_COLORS = ["bg-destructive", "bg-destructive", "bg-amber-500", "bg-amber-500", "bg-green-600"];

export function PasswordStrength({ password }: { password: string }) {
  const requirements = getPasswordRequirements(password);
  const strength = getPasswordStrength(password);

  const items = [
    { label: "At least 8 characters", met: requirements.minLength },
    { label: "Uppercase letter", met: requirements.hasUpper },
    { label: "Lowercase letter", met: requirements.hasLower },
    { label: "Number", met: requirements.hasNumber },
  ];

  return (
    <div className="space-y-2">
      <div className="flex gap-1" aria-hidden="true">
        {Array.from({ length: 4 }).map((_, i) => (
          <div
            key={i}
            className={cn("h-1 flex-1 rounded-full bg-muted", i < strength && STRENGTH_COLORS[strength])}
          />
        ))}
      </div>
      <p className="text-xs text-muted-foreground">
        Password strength: <span className="font-medium text-foreground">{STRENGTH_LABELS[strength]}</span>
      </p>
      <ul className="space-y-1">
        {items.map((item) => (
          <li key={item.label} className="flex items-center gap-1.5 text-xs">
            {item.met ? (
              <Check className="size-3.5 text-green-600" aria-hidden="true" />
            ) : (
              <X className="size-3.5 text-muted-foreground" aria-hidden="true" />
            )}
            <span className={item.met ? "text-foreground" : "text-muted-foreground"}>{item.label}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}
