/**
 * Centralized language registry for the multilingual architecture
 * (Milestone 1).
 *
 * This is the SINGLE source of truth for which languages the frontend
 * knows about. It mirrors backend/app/translation/languages.py
 * field-for-field -- kept in sync by a backend parity test
 * (backend/tests/test_language_registry.py). Never scatter language
 * checks (`if (code === "hi") ...`) through components; add or adjust a
 * language here instead.
 *
 * Two independent flags, deliberately not conflated:
 *
 *   - `enabled` -- whether the language has a static UI dictionary and
 *     can be chosen in the language selector. Milestone 1 enables
 *     exactly en/hi/bn; the other ten languages are registered (so
 *     adding one later is configuration-only, never an architecture
 *     change) but not yet selectable.
 *
 *   - `capabilities` -- whether the REAL, configured BHASHINI pipeline
 *     has been verified to support that language for that task. As of
 *     this milestone no BHASHINI credentials/pipeline have been
 *     configured or verified against the live API (see
 *     docs/architecture/multilingual-architecture.md), so every
 *     capability below is false for every language, including en/hi/bn.
 *     The mock translation provider is what makes dynamic-content
 *     translation work in this milestone regardless of these flags --
 *     flip a capability to true only after verifying that exact
 *     (language, task) pair against the actual BHASHINI account/
 *     pipeline, never speculatively.
 */

export type LanguageCode =
  | "en"
  | "hi"
  | "bn"
  | "ta"
  | "te"
  | "mr"
  | "gu"
  | "kn"
  | "ml"
  | "or"
  | "pa"
  | "as"
  | "ur";

export type Direction = "ltr" | "rtl";

export interface LanguageCapabilities {
  translation: boolean;
  speechToText: boolean;
  textToSpeech: boolean;
  transliteration: boolean;
}

export interface LanguageDefinition {
  code: LanguageCode;
  name: string;
  nativeName: string;
  locale: string;
  direction: Direction;
  enabled: boolean;
  capabilities: LanguageCapabilities;
}

const NO_CAPABILITIES: LanguageCapabilities = {
  translation: false,
  speechToText: false,
  textToSpeech: false,
  transliteration: false,
};

export const LANGUAGES: readonly LanguageDefinition[] = [
  { code: "en", name: "English", nativeName: "English", locale: "en-IN", direction: "ltr", enabled: true, capabilities: NO_CAPABILITIES },
  { code: "hi", name: "Hindi", nativeName: "हिन्दी", locale: "hi-IN", direction: "ltr", enabled: true, capabilities: NO_CAPABILITIES },
  { code: "bn", name: "Bengali", nativeName: "বাংলা", locale: "bn-IN", direction: "ltr", enabled: true, capabilities: NO_CAPABILITIES },
  { code: "ta", name: "Tamil", nativeName: "தமிழ்", locale: "ta-IN", direction: "ltr", enabled: false, capabilities: NO_CAPABILITIES },
  { code: "te", name: "Telugu", nativeName: "తెలుగు", locale: "te-IN", direction: "ltr", enabled: false, capabilities: NO_CAPABILITIES },
  { code: "mr", name: "Marathi", nativeName: "मराठी", locale: "mr-IN", direction: "ltr", enabled: false, capabilities: NO_CAPABILITIES },
  { code: "gu", name: "Gujarati", nativeName: "ગુજરાતી", locale: "gu-IN", direction: "ltr", enabled: false, capabilities: NO_CAPABILITIES },
  { code: "kn", name: "Kannada", nativeName: "ಕನ್ನಡ", locale: "kn-IN", direction: "ltr", enabled: false, capabilities: NO_CAPABILITIES },
  { code: "ml", name: "Malayalam", nativeName: "മലയാളം", locale: "ml-IN", direction: "ltr", enabled: false, capabilities: NO_CAPABILITIES },
  { code: "or", name: "Odia", nativeName: "ଓଡ଼ିଆ", locale: "or-IN", direction: "ltr", enabled: false, capabilities: NO_CAPABILITIES },
  { code: "pa", name: "Punjabi", nativeName: "ਪੰਜਾਬੀ", locale: "pa-IN", direction: "ltr", enabled: false, capabilities: NO_CAPABILITIES },
  { code: "as", name: "Assamese", nativeName: "অসমীয়া", locale: "as-IN", direction: "ltr", enabled: false, capabilities: NO_CAPABILITIES },
  { code: "ur", name: "Urdu", nativeName: "اردو", locale: "ur-IN", direction: "rtl", enabled: false, capabilities: NO_CAPABILITIES },
];

export const DEFAULT_LANGUAGE: LanguageCode = "en";

const BY_CODE = new Map<string, LanguageDefinition>(LANGUAGES.map((lang) => [lang.code, lang]));

/** One language definition by code, or undefined if unregistered. Never
 * throws -- callers decide whether an unknown code means "fall back to
 * English" or "reject the request". */
export function getLanguage(code: string): LanguageDefinition | undefined {
  return BY_CODE.get(code);
}

/** True only for a language that is both registered AND enabled -- the
 * check almost always wanted together (e.g. validating a persisted
 * language preference before applying it). */
export function isSupported(code: string): boolean {
  const lang = BY_CODE.get(code);
  return lang !== undefined && lang.enabled;
}

/** Every language currently selectable in the UI (Milestone 1:
 * en/hi/bn), in registry order. */
export function enabledLanguages(): LanguageDefinition[] {
  return LANGUAGES.filter((lang) => lang.enabled);
}

/** Every registered code, enabled or not. */
export function supportedCodes(): readonly string[] {
  return LANGUAGES.map((lang) => lang.code);
}

export function isRtl(code: string): boolean {
  return getLanguage(code)?.direction === "rtl";
}
