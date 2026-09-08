import { readFileSync } from "node:fs";
import { join } from "node:path";
import { describe, expect, it } from "vitest";

/**
 * Security guard (J5 spec §22 / §27): the Job Training frontend must go
 * frontend -> backend API -> RLS. It must never touch Supabase directly,
 * never reference the service role, and never talk to a raw fetch/URL.
 */

const ROOT = join(__dirname, "..", "..", "..", "..");

const FILES = [
  "lib/student/job-training.ts",
  "types/job-training.ts",
  "components/student/job-training/job-training-list-view.tsx",
  "components/student/job-training/job-training-detail-view.tsx",
  "components/student/job-training/job-training-program-content.tsx",
  "components/student/job-training/job-training-status-badge.tsx",
  "components/student/dashboard/dashboard-job-training.tsx",
  "app/student/job-training/page.tsx",
  "app/student/job-training/[enrollmentId]/page.tsx",
];

describe("Job Training frontend never touches the database directly", () => {
  for (const rel of FILES) {
    it(`${rel} uses only the backend API`, () => {
      const src = readFileSync(join(ROOT, rel), "utf8");

      expect(src).not.toMatch(/\.from\(["'`]job_training/);
      expect(src).not.toMatch(/supabase\.from/);
      expect(src).not.toMatch(/SERVICE_ROLE/);
      expect(src).not.toMatch(/@\/lib\/supabase\/client/);
      // client components never call fetch() directly -- everything goes
      // through lib/api.ts. (The route pages legitimately use the server
      // Supabase client only for the auth redirect, matching every other
      // student route.)
      if (!rel.startsWith("app/")) {
        expect(src).not.toMatch(/\bfetch\(/);
        expect(src).not.toMatch(/createClient/);
      }
    });
  }
});
