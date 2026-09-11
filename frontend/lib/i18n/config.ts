/**
 * Language resolution + persistence contract for the static i18n
 * foundation (Milestone 1). Deliberately framework-agnostic: no React,
 * no Next.js-specific imports -- this must stay usable from server
 * code, client code, and plain Vitest/Node tests alike, and from the
 * LanguageProvider that will consume it (a later step).
 *
 * Every browser API access (`document`, `window`, `navigator`) is
 * guarded so this module can be imported during SSR/static generation/
 * a jsdom-less Node test environment without throwing.
 */

import { DEFAULT_LANGUAGE as REGISTRY_DEFAULT_LANGUAGE, isSupported, type LanguageCode } from "@/lib/i18n/languages";

export const COOKIE_NAME = "aic_lang";
export const STORAGE_KEY = "aic_lang";

/** Re-exported from the language registry so callers only need one
 * import for "what language do we start in" -- see languages.ts for why
 * this is English. */
export const DEFAULT_LANGUAGE: LanguageCode = REGISTRY_DEFAULT_LANGUAGE;

/** True only for a code that is both registered AND enabled (see
 * languages.ts's own `enabled` vs `capabilities` distinction) --
 * narrows to LanguageCode so a caller never has to re-check. A
 * registered-but-disabled language (e.g. "ta" in Milestone 1) is
 * deliberately NOT valid here: it must never become the active
 * language automatically, only once it has a real dictionary and is
 * flipped to `enabled: true`. */
export function isValidLanguage(code: string | null | undefined): code is LanguageCode {
  return !!code && isSupported(code);
}

/** "bn-IN" -> "bn", "en-US" -> "en", "hi" -> "hi". Never throws on an
 * empty/malformed string -- returns it unchanged, which then simply
 * fails `isValidLanguage`. */
export function extractBaseLanguage(code: string): string {
  return code.split("-")[0]?.toLowerCase() ?? code;
}

// ============================================================
// Storage access -- kept separate from resolution/lookup so each half
// can be tested (and reasoned about) independently.
// ============================================================

/** Reads a cookie by name in the BROWSER only. Returns null during SSR/
 * static generation/Node tests (no `document`) and if the cookie isn't
 * set -- both are the same "nothing to use" signal to callers. */
export function readCookie(name: string): string | null {
  if (typeof document === "undefined") return null;
  const escaped = name.replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
  const match = document.cookie.match(new RegExp(`(?:^|; )${escaped}=([^;]*)`));
  return match ? decodeURIComponent(match[1]) : null;
}

/** Writes a cookie in the BROWSER only -- a no-op during SSR/static
 * generation/Node tests. One year expiry, readable from every path,
 * `SameSite=Lax` (a same-site language preference has no reason to be
 * sent cross-site). */
export function writeCookie(name: string, value: string): void {
  if (typeof document === "undefined") return;
  const maxAgeSeconds = 60 * 60 * 24 * 365;
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=${maxAgeSeconds}; SameSite=Lax`;
}

/** Reads localStorage in the BROWSER only. Returns null during SSR/
 * static generation/Node tests (no `window`) and also if access throws
 * (private-browsing modes and some embedded webviews block storage
 * access entirely) -- a blocked read must degrade to "no preference
 * found", never crash the app. */
export function readLocalStorage(key: string): string | null {
  if (typeof window === "undefined") return null;
  try {
    return window.localStorage.getItem(key);
  } catch {
    return null;
  }
}

/** Writes localStorage in the BROWSER only -- a no-op during SSR/static
 * generation/Node tests, and swallows a blocked/full-storage error
 * rather than throwing (the language still works for the current
 * session via in-memory state; only cross-session persistence is
 * lost). */
export function writeLocalStorage(key: string, value: string): void {
  if (typeof window === "undefined") return;
  try {
    window.localStorage.setItem(key, value);
  } catch {
    // Ignored on purpose -- see docstring above.
  }
}

/** Persists a chosen language to BOTH the cookie (so a server-rendered
 * page can read it on the next request) and localStorage (so a purely
 * client-side re-render picks it up immediately without waiting for a
 * navigation). Both writes are individually safe to call during SSR
 * (silent no-ops). */
export function persistLanguage(code: LanguageCode): void {
  writeCookie(COOKIE_NAME, code);
  writeLocalStorage(STORAGE_KEY, code);
}

/** The browser's most-preferred language tag (e.g. "bn-IN"), or null if
 * unavailable (SSR/static generation/Node tests, or a browser that
 * exposes neither `navigator.languages` nor `navigator.language`). */
function detectBrowserLanguage(): string | null {
  if (typeof navigator === "undefined") return null;
  if (Array.isArray(navigator.languages) && navigator.languages.length > 0) {
    return navigator.languages[0];
  }
  return navigator.language || null;
}

export interface ResolveLanguageOptions {
  /** An explicit override the caller already has in hand (e.g. a query
   * param, or a user's just-clicked selector choice) -- checked first,
   * ahead of any persisted preference. */
  explicit?: string | null;
  /** The `aic_lang` cookie's raw value, when the caller already has it
   * from a context this module can't reach itself (a Server Component
   * reading `next/headers`' `cookies()`). Client callers should use
   * `getInitialLanguage()` instead, which reads the cookie itself. */
  cookieValue?: string | null;
}

/**
 * The language-resolution order (Milestone 1 spec):
 *
 *   1. `explicit`, if valid
 *   2. `cookieValue` (the `aic_lang` cookie), if valid
 *   3. localStorage, if valid (browser only -- null elsewhere)
 *   4. the browser's own language, if it (or its base language) maps to
 *      a supported+enabled language (browser only -- null elsewhere)
 *   5. English
 *
 * "Valid" always means `isValidLanguage()`: registered AND enabled. A
 * registered-but-disabled language, or a code this app has never heard
 * of, is never returned here -- English is the only fallback.
 */
export function resolveLanguage(options: ResolveLanguageOptions = {}): LanguageCode {
  const { explicit, cookieValue } = options;

  if (isValidLanguage(explicit)) return explicit;
  if (isValidLanguage(cookieValue)) return cookieValue;

  const stored = readLocalStorage(STORAGE_KEY);
  if (isValidLanguage(stored)) return stored;

  const browserLanguage = detectBrowserLanguage();
  if (browserLanguage) {
    if (isValidLanguage(browserLanguage)) return browserLanguage;
    const base = extractBaseLanguage(browserLanguage);
    if (isValidLanguage(base)) return base;
  }

  return DEFAULT_LANGUAGE;
}

/**
 * Client-side convenience wrapper: resolves the language using
 * everything available in the browser (cookie + localStorage + browser
 * language), plus an optional explicit override. Safe to call during
 * SSR too -- every source it reads degrades to null there, so it
 * simply returns `DEFAULT_LANGUAGE`.
 */
export function getInitialLanguage(explicit?: string | null): LanguageCode {
  return resolveLanguage({
    explicit,
    cookieValue: readCookie(COOKIE_NAME),
  });
}
