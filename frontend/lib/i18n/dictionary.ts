/**
 * Static translation dictionary loader/lookup (Milestone 1).
 *
 * Deliberately framework-agnostic: no React import here either (see
 * config.ts's docstring for why) -- `useTranslation()` in a later step
 * is a thin React wrapper over `t()` below, nothing more.
 *
 * Dictionaries are plain JSON under frontend/locales/<code>/common.json,
 * statically imported (tree-shaken, bundled at build time, no runtime
 * fetch) -- this is the ONLY namespace file for Milestone 1; adding a
 * second namespace later (e.g. `navigation.json`) is a matter of
 * importing it and merging it into that language's entry in
 * `DICTIONARIES`, not an architecture change.
 *
 * English is the canonical source: every other dictionary is a subset
 * of its keys (possibly a proper subset, while a language is still
 * being translated) and is validated against it in
 * lib/i18n/__tests__/dictionary.test.ts, never the reverse.
 */

import bnCommon from "@/locales/bn/common.json";
import enCommon from "@/locales/en/common.json";
import hiCommon from "@/locales/hi/common.json";
import { DEFAULT_LANGUAGE } from "@/lib/i18n/config";

/** A dictionary is an arbitrarily (but in practice shallow, 2-3 level)
 * nested tree of string leaves -- matches the shape of the JSON files
 * above exactly. */
export type Dictionary = { [key: string]: string | Dictionary };

export const DICTIONARIES: Record<string, Dictionary> = {
  en: enCommon,
  hi: hiCommon,
  bn: bnCommon,
};

/** Derives every valid dot-path key from English's own shape (e.g.
 * "common.appName" | "navigation.dashboard" | ...) so `t()` calls are
 * checked against real keys at compile time, without hand-maintaining a
 * separate key enum that could drift from the actual dictionary. Not a
 * runtime value -- purely a compile-time type. */
type DotPaths<T> = T extends string
  ? never
  : { [K in keyof T & string]: T[K] extends string ? K : `${K}.${DotPaths<T[K]>}` }[keyof T & string];

export type TranslationKey = DotPaths<typeof enCommon>;

export type InterpolationVars = Record<string, string | number>;

function getPath(dict: Dictionary, key: string): string | undefined {
  const parts = key.split(".");
  let current: string | Dictionary = dict;
  for (const part of parts) {
    if (typeof current !== "object" || current === null || !(part in current)) {
      return undefined;
    }
    current = current[part];
  }
  return typeof current === "string" ? current : undefined;
}

function interpolate(template: string, vars: InterpolationVars): string {
  return template.replace(/\{\{(\w+)\}\}/g, (match, name: string) => {
    const value = vars[name];
    return value === undefined ? match : String(value);
  });
}

function warnMissingTranslation(key: string, language: string, foundInEnglish: boolean): void {
  if (process.env.NODE_ENV === "production") return;
  if (foundInEnglish) {
    console.warn(`[i18n] "${key}" has no ${language} translation yet -- using English.`);
  } else {
    console.warn(`[i18n] "${key}" does not exist in any dictionary (requested language: ${language}).`);
  }
}

/**
 * The core lookup, parameterized over an explicit dictionary map so
 * tests can exercise fallback/interpolation behavior against small
 * synthetic dictionaries instead of the real (and growing) seed
 * content. `t()` below is this, pinned to the real `DICTIONARIES`.
 *
 * Resolution order for one key:
 *   1. `dictionaries[language]` -- if the key exists there, return it.
 *   2. `dictionaries[DEFAULT_LANGUAGE]` (English) -- if the key exists
 *      there, return it (with a dev-only warning: language is missing
 *      a translation that needs adding).
 *   3. Neither has it -- return the key itself, unchanged, and warn.
 *      NEVER returns undefined, NEVER throws -- a typo'd or not-yet-
 *      seeded key must degrade to visible-but-wrong text, not a
 *      crashed render.
 */
export function translateWithDictionaries(
  dictionaries: Record<string, Dictionary>,
  language: string,
  key: string,
  vars?: InterpolationVars,
): string {
  const requestedDict = dictionaries[language];
  let value = requestedDict ? getPath(requestedDict, key) : undefined;

  if (value === undefined) {
    const englishDict = dictionaries[DEFAULT_LANGUAGE];
    const englishValue = englishDict ? getPath(englishDict, key) : undefined;
    if (englishValue !== undefined) {
      if (language !== DEFAULT_LANGUAGE) warnMissingTranslation(key, language, true);
      value = englishValue;
    } else {
      warnMissingTranslation(key, language, false);
      return key;
    }
  }

  return vars ? interpolate(value, vars) : value;
}

/** The real, public lookup function -- `t("navigation.dashboard")`,
 * `t("dashboard.welcomeUser", { name: "Rahul" })`. `key` is typed as
 * `TranslationKey`, derived from English's real shape above, so a
 * typo'd or invented key is a compile-time error, not a silent runtime
 * fallback -- callers that genuinely need a dynamic/non-literal key can
 * use `translateWithDictionaries(DICTIONARIES, ...)` directly instead.
 * See `translateWithDictionaries` above for the exact fallback
 * contract. */
export function t(language: string, key: TranslationKey, vars?: InterpolationVars): string {
  return translateWithDictionaries(DICTIONARIES, language, key, vars);
}
