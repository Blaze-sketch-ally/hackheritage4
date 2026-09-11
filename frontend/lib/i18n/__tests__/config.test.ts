import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import {
  COOKIE_NAME,
  DEFAULT_LANGUAGE,
  STORAGE_KEY,
  extractBaseLanguage,
  getInitialLanguage,
  isValidLanguage,
  persistLanguage,
  readCookie,
  readLocalStorage,
  resolveLanguage,
  writeCookie,
  writeLocalStorage,
} from "@/lib/i18n/config";

function clearCookie(name: string) {
  document.cookie = `${name}=; path=/; max-age=0`;
}

function setNavigatorLanguage(language: string, languages: string[] = [language]) {
  Object.defineProperty(window.navigator, "language", { value: language, configurable: true });
  Object.defineProperty(window.navigator, "languages", { value: languages, configurable: true });
}

beforeEach(() => {
  window.localStorage.clear();
  clearCookie(COOKIE_NAME);
  setNavigatorLanguage("en-US");
});

afterEach(() => {
  window.localStorage.clear();
  clearCookie(COOKIE_NAME);
});

// ============================================================
// isValidLanguage / extractBaseLanguage
// ============================================================

describe("isValidLanguage", () => {
  it("accepts an enabled language code", () => {
    expect(isValidLanguage("hi")).toBe(true);
    expect(isValidLanguage("bn")).toBe(true);
    expect(isValidLanguage("en")).toBe(true);
  });

  it("rejects a registered-but-disabled language code", () => {
    // "ta" (Tamil) is registered in the language registry but not yet
    // enabled in Milestone 1 -- must never validate as selectable.
    expect(isValidLanguage("ta")).toBe(false);
  });

  it("rejects a code the registry has never heard of", () => {
    expect(isValidLanguage("xx")).toBe(false);
  });

  it("rejects null/undefined/empty without throwing", () => {
    expect(isValidLanguage(null)).toBe(false);
    expect(isValidLanguage(undefined)).toBe(false);
    expect(isValidLanguage("")).toBe(false);
  });
});

describe("extractBaseLanguage", () => {
  it("strips a regional suffix", () => {
    expect(extractBaseLanguage("en-US")).toBe("en");
    expect(extractBaseLanguage("en-GB")).toBe("en");
    expect(extractBaseLanguage("hi-IN")).toBe("hi");
    expect(extractBaseLanguage("bn-IN")).toBe("bn");
  });

  it("passes through a code with no region", () => {
    expect(extractBaseLanguage("hi")).toBe("hi");
  });
});

// ============================================================
// resolveLanguage -- the full priority order
// ============================================================

describe("resolveLanguage", () => {
  it("prefers an explicit valid language over everything else", () => {
    writeCookie(COOKIE_NAME, "bn");
    window.localStorage.setItem(STORAGE_KEY, "hi");
    setNavigatorLanguage("bn-IN");

    expect(resolveLanguage({ explicit: "en", cookieValue: readCookie(COOKIE_NAME) })).toBe("en");
  });

  it("falls through an invalid explicit language to the next source", () => {
    expect(resolveLanguage({ explicit: "xx", cookieValue: "hi" })).toBe("hi");
  });

  it("uses a valid cookie value when there is no explicit override", () => {
    expect(resolveLanguage({ cookieValue: "bn" })).toBe("bn");
  });

  it("ignores an invalid cookie value and falls through", () => {
    window.localStorage.setItem(STORAGE_KEY, "hi");
    expect(resolveLanguage({ cookieValue: "xx" })).toBe("hi");
  });

  it("uses a valid localStorage value when there is no explicit/cookie preference", () => {
    window.localStorage.setItem(STORAGE_KEY, "bn");
    expect(resolveLanguage({})).toBe("bn");
  });

  it("ignores an invalid localStorage value and falls through to the browser language", () => {
    window.localStorage.setItem(STORAGE_KEY, "xx");
    setNavigatorLanguage("hi-IN");
    expect(resolveLanguage({})).toBe("hi");
  });

  it("uses an exact-match browser language", () => {
    setNavigatorLanguage("bn");
    expect(resolveLanguage({})).toBe("bn");
  });

  it("resolves a regional browser language to its base language", () => {
    // Given browser language "bn-IN", resolveLanguage() returns "bn".
    setNavigatorLanguage("bn-IN");
    expect(resolveLanguage({})).toBe("bn");
  });

  it("resolves en-GB and en-US to en", () => {
    setNavigatorLanguage("en-GB");
    expect(resolveLanguage({})).toBe("en");
    setNavigatorLanguage("en-US");
    expect(resolveLanguage({})).toBe("en");
  });

  it("never auto-selects a registered-but-disabled language from any source", () => {
    expect(resolveLanguage({ explicit: "ta" })).toBe(DEFAULT_LANGUAGE);
    expect(resolveLanguage({ cookieValue: "ta" })).toBe(DEFAULT_LANGUAGE);

    window.localStorage.setItem(STORAGE_KEY, "ta");
    expect(resolveLanguage({})).toBe(DEFAULT_LANGUAGE);

    window.localStorage.clear();
    setNavigatorLanguage("ta-IN");
    expect(resolveLanguage({})).toBe(DEFAULT_LANGUAGE);
  });

  it("falls back to English for a browser language the registry has never heard of", () => {
    setNavigatorLanguage("xx-YY");
    expect(resolveLanguage({})).toBe(DEFAULT_LANGUAGE);
  });

  it("falls back to English when no preference exists anywhere", () => {
    Object.defineProperty(window.navigator, "language", { value: "", configurable: true });
    Object.defineProperty(window.navigator, "languages", { value: [], configurable: true });
    expect(resolveLanguage({})).toBe("en");
    expect(resolveLanguage({})).toBe(DEFAULT_LANGUAGE);
  });
});

// ============================================================
// getInitialLanguage -- the browser convenience wrapper
// ============================================================

describe("getInitialLanguage", () => {
  it("reads the aic_lang cookie itself", () => {
    writeCookie(COOKIE_NAME, "hi");
    expect(getInitialLanguage()).toBe("hi");
  });

  it("accepts an explicit override ahead of the cookie", () => {
    writeCookie(COOKIE_NAME, "hi");
    expect(getInitialLanguage("bn")).toBe("bn");
  });

  it("falls back through localStorage and the browser language, same as resolveLanguage", () => {
    window.localStorage.setItem(STORAGE_KEY, "bn");
    expect(getInitialLanguage()).toBe("bn");
  });
});

// ============================================================
// SSR safety -- no window / document / navigator / localStorage
// ============================================================

describe("SSR safety", () => {
  it("readCookie returns null without `document`", () => {
    vi.stubGlobal("document", undefined);
    expect(() => readCookie(COOKIE_NAME)).not.toThrow();
    expect(readCookie(COOKIE_NAME)).toBeNull();
    vi.unstubAllGlobals();
  });

  it("writeCookie is a silent no-op without `document`", () => {
    vi.stubGlobal("document", undefined);
    expect(() => writeCookie(COOKIE_NAME, "hi")).not.toThrow();
    vi.unstubAllGlobals();
  });

  it("readLocalStorage returns null without `window`", () => {
    vi.stubGlobal("window", undefined);
    expect(() => readLocalStorage(STORAGE_KEY)).not.toThrow();
    expect(readLocalStorage(STORAGE_KEY)).toBeNull();
    vi.unstubAllGlobals();
  });

  it("writeLocalStorage is a silent no-op without `window`", () => {
    vi.stubGlobal("window", undefined);
    expect(() => writeLocalStorage(STORAGE_KEY, "hi")).not.toThrow();
    vi.unstubAllGlobals();
  });

  it("resolveLanguage never throws without window/document/navigator and falls back to English", () => {
    vi.stubGlobal("window", undefined);
    vi.stubGlobal("document", undefined);
    vi.stubGlobal("navigator", undefined);
    expect(() => resolveLanguage({})).not.toThrow();
    expect(resolveLanguage({})).toBe(DEFAULT_LANGUAGE);
    vi.unstubAllGlobals();
  });

  it("getInitialLanguage never throws without document", () => {
    vi.stubGlobal("document", undefined);
    expect(() => getInitialLanguage()).not.toThrow();
    expect(getInitialLanguage()).toBe(DEFAULT_LANGUAGE);
    vi.unstubAllGlobals();
  });

  it("persistLanguage never throws without window/document", () => {
    vi.stubGlobal("window", undefined);
    vi.stubGlobal("document", undefined);
    expect(() => persistLanguage("hi")).not.toThrow();
    vi.unstubAllGlobals();
  });

  it("resolveLanguage still honors an explicitly-passed cookieValue even without document", () => {
    // The whole point of accepting `cookieValue` as an option (rather
    // than always reading `document.cookie` itself) is so a Server
    // Component that already has the cookie from `next/headers` can use
    // this function without `document` ever existing.
    vi.stubGlobal("document", undefined);
    vi.stubGlobal("window", undefined);
    vi.stubGlobal("navigator", undefined);
    expect(resolveLanguage({ cookieValue: "bn" })).toBe("bn");
    vi.unstubAllGlobals();
  });
});

// ============================================================
// Persistence helpers
// ============================================================

describe("cookie read/write", () => {
  it("round-trips a value written with writeCookie", () => {
    expect(readCookie(COOKIE_NAME)).toBeNull();
    writeCookie(COOKIE_NAME, "bn");
    expect(readCookie(COOKIE_NAME)).toBe("bn");
  });

  it("URL-encodes and decodes the value", () => {
    writeCookie(COOKIE_NAME, "hi");
    expect(document.cookie).toContain(`${COOKIE_NAME}=hi`);
    expect(readCookie(COOKIE_NAME)).toBe("hi");
  });
});

describe("localStorage read/write", () => {
  it("round-trips a value written with writeLocalStorage", () => {
    expect(readLocalStorage(STORAGE_KEY)).toBeNull();
    writeLocalStorage(STORAGE_KEY, "bn");
    expect(readLocalStorage(STORAGE_KEY)).toBe("bn");
  });
});

describe("persistLanguage", () => {
  it("writes both the cookie and localStorage", () => {
    persistLanguage("bn");
    expect(readCookie(COOKIE_NAME)).toBe("bn");
    expect(readLocalStorage(STORAGE_KEY)).toBe("bn");
  });
});
