import { describe, expect, it, vi } from "vitest";
import { DICTIONARIES, t, translateWithDictionaries, type Dictionary } from "@/lib/i18n/dictionary";

describe("t() against the real seed dictionaries", () => {
  it("returns the English value for an English key", () => {
    expect(t("en", "navigation.dashboard")).toBe("Dashboard");
  });

  it("returns the Hindi value when the key exists in Hindi", () => {
    // Given requested language = "hi", key = "navigation.dashboard", the
    // Hindi dictionary is used.
    expect(t("hi", "navigation.dashboard")).toBe("डैशबोर्ड");
  });

  it("returns the Bengali value when the key exists in Bengali", () => {
    expect(t("bn", "navigation.dashboard")).toBe("ড্যাশবোর্ড");
  });

  it("resolves a nested key path (namespace.key) correctly for every seeded language", () => {
    expect(t("en", "common.selectLanguage")).toBe("Select language");
    expect(t("hi", "common.selectLanguage")).toBe("भाषा चुनें");
    expect(t("bn", "common.selectLanguage")).toBe("ভাষা নির্বাচন করুন");
  });

  it("falls back to English when a key is missing from Hindi", () => {
    // "common.betaLabel" is deliberately seeded in English only, to
    // exercise this exact fallback path against real dictionary
    // content, not just a synthetic fixture.
    expect(DICTIONARIES.hi).not.toHaveProperty("common.betaLabel");
    expect(t("hi", "common.betaLabel")).toBe(t("en", "common.betaLabel"));
    expect(t("hi", "common.betaLabel")).toBe("Beta");
  });

  it("falls back to English when a key is missing from Bengali", () => {
    expect(t("bn", "common.betaLabel")).toBe("Beta");
  });

  it("interpolates a variable into the requested language's string", () => {
    expect(t("en", "dashboard.welcomeUser", { name: "Rahul" })).toBe("Welcome, Rahul!");
    expect(t("hi", "dashboard.welcomeUser", { name: "Rahul" })).toBe("स्वागत है, Rahul!");
    expect(t("bn", "dashboard.welcomeUser", { name: "Rahul" })).toBe("স্বাগতম, Rahul!");
  });
});

describe("translateWithDictionaries against synthetic dictionaries", () => {
  const dictionaries: Record<string, Dictionary> = {
    en: { greeting: { hello: "Hello", welcome: "Welcome, {{name}}!" } },
    hi: { greeting: { hello: "नमस्ते" } },
  };

  it("uses the requested language's value when present", () => {
    expect(translateWithDictionaries(dictionaries, "hi", "greeting.hello")).toBe("नमस्ते");
  });

  it("falls back to English for a key missing in the requested (known) language", () => {
    // "hi" exists as a dictionary but has no "greeting.welcome" key.
    expect(translateWithDictionaries(dictionaries, "hi", "greeting.welcome", { name: "Priya" })).toBe(
      "Welcome, Priya!",
    );
  });

  it("falls back to English for a language with no dictionary at all", () => {
    // Given requested language = "xx", the result is English.
    expect(translateWithDictionaries(dictionaries, "xx", "greeting.hello")).toBe("Hello");
  });

  it("returns the key itself, never undefined, when the key exists nowhere", () => {
    expect(translateWithDictionaries(dictionaries, "en", "greeting.missing")).toBe("greeting.missing");
    expect(translateWithDictionaries(dictionaries, "hi", "does.not.exist")).toBe("does.not.exist");
  });

  it("never throws for a missing key", () => {
    expect(() => translateWithDictionaries(dictionaries, "hi", "totally.made.up")).not.toThrow();
  });

  it("interpolates multiple variables and leaves an unmatched placeholder untouched", () => {
    const dict: Record<string, Dictionary> = {
      en: { msg: "{{greeting}}, {{name}}! You have {{count}} items." },
    };
    expect(
      translateWithDictionaries(dict, "en", "msg", { greeting: "Hi", name: "Sam", count: 3 }),
    ).toBe("Hi, Sam! You have 3 items.");
    // A variable the caller didn't supply is left as the raw token
    // rather than silently becoming an empty string or crashing.
    expect(translateWithDictionaries(dict, "en", "msg", { greeting: "Hi" })).toBe(
      "Hi, {{name}}! You have {{count}} items.",
    );
  });

  it("returns the template unchanged when no vars are supplied to an interpolated string", () => {
    const dict: Record<string, Dictionary> = { en: { msg: "Hello, {{name}}!" } };
    expect(translateWithDictionaries(dict, "en", "msg")).toBe("Hello, {{name}}!");
  });

  it("does not treat a non-string leaf (or a missing intermediate object) as a value", () => {
    const dict: Record<string, Dictionary> = { en: { nested: { deeper: "leaf" } } };
    // Requesting the intermediate object itself, not a leaf -- must not
    // return "[object Object]" or throw, only ever a safe string.
    expect(translateWithDictionaries(dict, "en", "nested")).toBe("nested");
    expect(translateWithDictionaries(dict, "en", "nested.deeper")).toBe("leaf");
  });
});

describe("dev-only missing-translation warnings", () => {
  it("warns (but does not throw) when falling back from a known language to English", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const originalEnv = process.env.NODE_ENV;
    // @ts-expect-error -- test-only override of a normally-readonly env var
    process.env.NODE_ENV = "development";

    expect(t("hi", "common.betaLabel")).toBe("Beta");
    expect(warnSpy).toHaveBeenCalled();

    // @ts-expect-error -- restoring the test-only override
    process.env.NODE_ENV = originalEnv;
    warnSpy.mockRestore();
  });

  it("does not warn in production", () => {
    const warnSpy = vi.spyOn(console, "warn").mockImplementation(() => {});
    const originalEnv = process.env.NODE_ENV;
    // @ts-expect-error -- test-only override of a normally-readonly env var
    process.env.NODE_ENV = "production";

    expect(t("hi", "common.betaLabel")).toBe("Beta");
    expect(warnSpy).not.toHaveBeenCalled();

    // @ts-expect-error -- restoring the test-only override
    process.env.NODE_ENV = originalEnv;
    warnSpy.mockRestore();
  });
});

describe("dictionary shape sanity", () => {
  it("registers exactly the Milestone-1 languages", () => {
    expect(Object.keys(DICTIONARIES).sort()).toEqual(["bn", "en", "hi"]);
  });

  it("every non-English dictionary is a subset of English's keys (no orphaned translations)", () => {
    function flatten(dict: Dictionary, prefix = ""): string[] {
      return Object.entries(dict).flatMap(([key, value]) => {
        const path = prefix ? `${prefix}.${key}` : key;
        return typeof value === "string" ? [path] : flatten(value, path);
      });
    }
    const englishKeys = new Set(flatten(DICTIONARIES.en));
    for (const [code, dict] of Object.entries(DICTIONARIES)) {
      if (code === "en") continue;
      for (const key of flatten(dict)) {
        expect(englishKeys.has(key), `${code} has key "${key}" that does not exist in English`).toBe(true);
      }
    }
  });
});
