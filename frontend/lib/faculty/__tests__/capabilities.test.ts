import { describe, expect, it } from "vitest";
import { hasAssessmentCapability, type AssessmentCapability } from "@/lib/faculty/capabilities";

describe("hasAssessmentCapability", () => {
  it("does not imply one assessment capability from another", () => {
    const capabilities: AssessmentCapability[] = ["assessment_author"];

    expect(hasAssessmentCapability(capabilities, "assessment_author")).toBe(true);
    expect(hasAssessmentCapability(capabilities, "assessment_reviewer")).toBe(false);
    expect(hasAssessmentCapability(capabilities, "assessment_evaluator")).toBe(false);
  });
});
