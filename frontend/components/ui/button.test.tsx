import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * Regression guard for QA finding F1-1.
 *
 * Base UI's `<Button>` assumes `nativeButton` is `true` — that a `render`
 * prop still resolves to a real `<button>`. When callers pass a
 * non-`<button>` element (overwhelmingly `render={<Link .../>}`, which
 * renders an `<a>`), Base UI logs a dev-only console.error and applies
 * `type="button"` instead of `role="button"`. Our wrapper defaults
 * `nativeButton` to `false` for that case. These tests lock that contract
 * in so a wrapper revert fails loudly.
 */
describe("Button — nativeButton auto-detection (F1-1)", () => {
  afterEach(() => vi.restoreAllMocks());

  function nativeButtonWarnings(spy: ReturnType<typeof vi.spyOn>) {
    return spy.mock.calls.filter((args: unknown[]) =>
      args.some((a) => typeof a === "string" && a.includes("expected a native <button>")),
    );
  }

  it("renders a plain <button> unchanged (no render prop)", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(<Button>Click me</Button>);
    const el = screen.getByRole("button", { name: "Click me" });
    expect(el.tagName).toBe("BUTTON");
    expect(el).toHaveAttribute("type", "button");
    expect(nativeButtonWarnings(errorSpy)).toEqual([]);
  });

  it("renders render={<Link/>} as an <a href> with role=button and no native-button error", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(<Button render={<Link href="/somewhere" />}>Go</Button>);
    const el = screen.getByRole("button", { name: "Go" });
    expect(el.tagName).toBe("A");
    expect(el).toHaveAttribute("href", "/somewhere");
    expect(el).not.toHaveAttribute("type");
    expect(nativeButtonWarnings(errorSpy)).toEqual([]);
  });

  it("still renders a real <button> passed via render={<button/>} as native", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    render(<Button render={<button type="submit" />}>Submit</Button>);
    const el = screen.getByRole("button", { name: "Submit" });
    expect(el.tagName).toBe("BUTTON");
    expect(nativeButtonWarnings(errorSpy)).toEqual([]);
  });

  it("honours an explicit nativeButton prop over the auto-default", () => {
    const errorSpy = vi.spyOn(console, "error").mockImplementation(() => {});
    // Explicit nativeButton={true} on a non-button is a caller mistake; the
    // wrapper must not silently override it — Base UI then warns as designed.
    render(
      <Button render={<Link href="/x" />} nativeButton={true}>
        Bad
      </Button>,
    );
    expect(nativeButtonWarnings(errorSpy).length).toBeGreaterThan(0);
  });
});
