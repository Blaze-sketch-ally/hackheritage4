import "@testing-library/jest-dom/vitest";

// jsdom implements neither ResizeObserver nor Element.hasPointerCapture --
// Base UI's Select (components/ui/select.tsx) uses both for its
// popup-anchor positioning, and their absence otherwise leaves any test
// that opens a Select stuck retrying indefinitely instead of failing
// fast or working. Minimal no-op stubs, matching the standard workaround
// for testing Radix/Base-UI-style positioned popups under jsdom.
if (typeof globalThis.ResizeObserver === "undefined") {
  globalThis.ResizeObserver = class ResizeObserver {
    observe() {}
    unobserve() {}
    disconnect() {}
  };
}
if (typeof Element !== "undefined" && !Element.prototype.hasPointerCapture) {
  Element.prototype.hasPointerCapture = () => false;
}
if (typeof Element !== "undefined" && !Element.prototype.scrollIntoView) {
  Element.prototype.scrollIntoView = () => {};
}
