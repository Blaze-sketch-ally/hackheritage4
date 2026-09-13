"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";
import type { ComponentProps } from "react";

/** Thin wrapper so the rest of the app never imports next-themes directly.
 * Mounted once in the root layout — persists the user's choice in
 * localStorage (next-themes' default `theme` key) and toggles the `.dark`
 * class on `<html>` that app/globals.css's `@custom-variant dark` reads. */
export function ThemeProvider({ children, ...props }: ComponentProps<typeof NextThemesProvider>) {
  return <NextThemesProvider {...props}>{children}</NextThemesProvider>;
}
