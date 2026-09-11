"use client";

import * as React from "react";
import { useTheme } from "next-themes";
import { Laptop, Moon, Sun } from "lucide-react";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

const emptySubscribe = () => () => {};

export function ThemeToggle({ className }: { className?: string }) {
  const { setTheme, theme } = useTheme();
  const mounted = React.useSyncExternalStore(emptySubscribe, () => true, () => false);

  if (!mounted) {
    return (
      <Button
        variant="ghost"
        size="icon"
        className={className}
        aria-label="Toggle theme"
        disabled
      >
        <Sun className="size-4 opacity-50" />
      </Button>
    );
  }

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        className="inline-flex size-9 items-center justify-center rounded-lg text-muted-foreground transition-colors hover:bg-muted hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        aria-label="Select theme"
      >
        {theme === "dark" ? (
          <Moon className="size-4" />
        ) : theme === "light" ? (
          <Sun className="size-4" />
        ) : (
          <Laptop className="size-4" />
        )}
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end">
        <DropdownMenuItem onClick={() => setTheme("light")} className="gap-2 cursor-pointer">
          <Sun className="size-4" /> Light
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("dark")} className="gap-2 cursor-pointer">
          <Moon className="size-4" /> Dark
        </DropdownMenuItem>
        <DropdownMenuItem onClick={() => setTheme("system")} className="gap-2 cursor-pointer">
          <Laptop className="size-4" /> System
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
