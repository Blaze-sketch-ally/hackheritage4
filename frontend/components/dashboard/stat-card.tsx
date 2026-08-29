import type { LucideIcon } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

export interface StatCardProps {
  label: string;
  value: string;
  helperText?: string;
  icon: LucideIcon;
  trend?: "up" | "down" | "neutral";
  accent?: "indigo" | "violet" | "blue" | "emerald" | "amber";
}

const ACCENTS: Record<NonNullable<StatCardProps["accent"]>, string> = {
  indigo: "bg-indigo-500/10 text-indigo-600 dark:text-indigo-400",
  violet: "bg-violet-500/10 text-violet-600 dark:text-violet-400",
  blue: "bg-blue-500/10 text-blue-600 dark:text-blue-400",
  emerald: "bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  amber: "bg-amber-500/10 text-amber-600 dark:text-amber-400",
};

export function StatCard({
  label,
  value,
  helperText,
  icon: Icon,
  trend = "neutral",
  accent = "indigo",
}: StatCardProps) {
  return (
    <Card>
      <CardContent className="flex items-start justify-between gap-3">
        <div className="space-y-1">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className="text-2xl font-semibold tracking-tight">{value}</p>
          {helperText ? (
            <p
              className={cn(
                "text-xs font-medium",
                trend === "up" && "text-emerald-600 dark:text-emerald-400",
                trend === "down" && "text-destructive",
                trend === "neutral" && "text-muted-foreground",
              )}
            >
              {trend === "up" ? "↑ " : trend === "down" ? "↓ " : ""}
              {helperText}
            </p>
          ) : null}
        </div>
        <span className={cn("flex size-9 shrink-0 items-center justify-center rounded-lg", ACCENTS[accent])}>
          <Icon className="size-4.5" aria-hidden="true" />
        </span>
      </CardContent>
    </Card>
  );
}
