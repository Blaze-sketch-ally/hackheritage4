"use client";

import { useEffect, useState } from "react";
import { Monitor, Moon, Sun } from "lucide-react";
import { useTheme } from "next-themes";
import { Button } from "@/components/ui/button";

const CYCLE = ["light", "dark", "system"] as const;
type ThemeChoice = (typeof CYCLE)[number];

const ICON = { light: Sun, dark: Moon, system: Monitor } as const;
const NEXT_LABEL: Record<ThemeChoice, string> = {
  light: "dark",
  dark: "system",
  system: "light",
};

/** The ONE global theme switcher, mounted once per role header (Student /
 * Industry / Institution). A single compact button cycles
 * light → dark → system so all three explicit states stay reachable
 * without a popover. `mounted` guards against a hydration mismatch: only
 * the client knows the real resolved theme (the server has no
 * localStorage/matchMedia access), so this renders a neutral Sun for one
 * tick rather than guessing and flipping right after hydration. */
export function ThemeToggle() {
  const { theme, setTheme, resolvedTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Standard next-themes hydration guard: the server can't know the real
  // theme (no localStorage/matchMedia), so this renders a neutral Sun for
  // exactly one client tick instead of guessing and flashing the wrong icon.
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => setMounted(true), []);

  const current: ThemeChoice = mounted ? ((theme as ThemeChoice) ?? "system") : "light";
  const Icon = mounted ? (ICON[current] ?? (resolvedTheme === "dark" ? Moon : Sun)) : Sun;
  const label = mounted
    ? `Theme: ${current} — click for ${NEXT_LABEL[current]}`
    : "Change theme";

  function cycle() {
    const i = CYCLE.indexOf(current);
    setTheme(CYCLE[(i + 1) % CYCLE.length]);
  }

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={label}
      title={label}
      onClick={cycle}
      className="text-muted-foreground hover:text-foreground"
    >
      <Icon className="size-4" aria-hidden="true" />
    </Button>
  );
}
