import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

/** "1350" -> "1.3K", "125000" -> "125K", "1200000" -> "1.2M". Display
 * formatting only -- never implies a raw count means academic quality;
 * callers decide whether/how prominently to show it. Locale is fixed
 * to "en-US" (not the viewer's locale) so the K/M form is consistent
 * regardless of runtime/browser locale -- compact notation otherwise
 * varies by locale (e.g. Hindi uses Lakh/Crore grouping). */
export function formatCompactCount(count: number): string {
  return Intl.NumberFormat("en-US", { notation: "compact", maximumFractionDigits: 1 }).format(count);
}
