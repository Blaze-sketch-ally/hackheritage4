import { defineConfig } from "vitest/config";
import react from "@vitejs/plugin-react";
import path from "node:path";

// Minimal Vitest setup added for the assessment-taking UI phase — this
// project previously had no frontend test framework at all. Mirrors
// tsconfig.json's "@/*" -> "./*" path alias so imports match app code
// exactly; jsdom environment is needed for React Testing Library.
export default defineConfig({
  plugins: [react()],
  test: {
    environment: "jsdom",
    setupFiles: ["./vitest.setup.ts"],
    globals: true,
  },
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "."),
    },
  },
});
