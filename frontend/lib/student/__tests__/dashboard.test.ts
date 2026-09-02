import { describe, expect, it } from "vitest";
import {
  summarizeApplications,
  summarizeAssessments,
  summarizeLearning,
  summarizeSkills,
  toReadinessDisplay,
} from "@/lib/student/dashboard";
import type { StudentSkill } from "@/lib/student/skills";
import type { StudentApplication } from "@/types/student-opportunity";
import type { StudentLearningResource } from "@/types/student-learning";
import type { AttemptHistoryItem } from "@/types/assessment";
import type { SkillGapJobRoleAnalysis, SkillGapPersonalAnalysis } from "@/types/skill-gap";

function skill(overrides: Partial<StudentSkill> = {}): StudentSkill {
  return {
    id: crypto.randomUUID(),
    skill_id: "s",
    proficiency_level: "Beginner",
    proficiency_score: null,
    is_verified: false,
    created_at: "",
    updated_at: "",
    skill: { id: "s", name: "X", description: null, category: null },
    ...overrides,
  } as StudentSkill;
}

function application(status: StudentApplication["status"]): StudentApplication {
  return {
    id: crypto.randomUUID(),
    student_id: "me",
    opportunity_type: "INTERNSHIP",
    internship_id: "i",
    job_id: null,
    status,
    cover_note: null,
    match_score: null,
    applied_at: null,
    created_at: null,
    updated_at: null,
    opportunity: null,
  };
}

function progress(status: StudentLearningResource["status"]): StudentLearningResource {
  return {
    resource_id: crypto.randomUUID(),
    status,
    started_at: null,
    completed_at: null,
    created_at: null,
    updated_at: null,
    resource: null,
  };
}

function attempt(overrides: Partial<AttemptHistoryItem> = {}): AttemptHistoryItem {
  return {
    id: crypto.randomUUID(),
    status: "COMPLETED",
    started_at: "",
    submitted_at: null,
    score: null,
    total_marks: null,
    percentage: null,
    passed: null,
    skill_verified: null,
    assessment: null,
    ...overrides,
  };
}

describe("summarizeSkills", () => {
  it("counts total, verified, and the proficiency distribution from real rows", () => {
    const s = summarizeSkills([
      skill({ proficiency_level: "Beginner" }),
      skill({ proficiency_level: "Advanced", is_verified: true }),
      skill({ proficiency_level: "Advanced" }),
      skill({ proficiency_level: "Expert", is_verified: true }),
    ]);
    expect(s.total).toBe(4);
    expect(s.verified).toBe(2);
    expect(s.byLevel).toEqual({ Beginner: 1, Intermediate: 0, Advanced: 2, Expert: 1 });
  });

  it("is all zeros for a student with no skills", () => {
    expect(summarizeSkills([])).toEqual({
      total: 0,
      verified: 0,
      byLevel: { Beginner: 0, Intermediate: 0, Advanced: 0, Expert: 0 },
    });
  });
});

describe("summarizeApplications", () => {
  it("groups by the seven live statuses and derives active/selected", () => {
    const s = summarizeApplications([
      application("APPLIED"),
      application("UNDER_REVIEW"),
      application("SHORTLISTED"),
      application("INTERVIEW_SCHEDULED"),
      application("SELECTED"),
      application("REJECTED"),
      application("WITHDRAWN"),
    ]);
    expect(s.total).toBe(7);
    expect(s.active).toBe(4); // APPLIED + UNDER_REVIEW + SHORTLISTED + INTERVIEW_SCHEDULED
    expect(s.selected).toBe(1);
    expect(s.rejected).toBe(1);
    expect(s.byStatus.WITHDRAWN).toBe(1);
  });

  it("is empty for a student with no applications", () => {
    const s = summarizeApplications([]);
    expect(s.total).toBe(0);
    expect(s.active).toBe(0);
    expect(s.selected).toBe(0);
  });
});

describe("summarizeLearning", () => {
  it("counts only the three real progress statuses", () => {
    const s = summarizeLearning([
      progress("SAVED"),
      progress("SAVED"),
      progress("IN_PROGRESS"),
      progress("COMPLETED"),
    ]);
    expect(s).toEqual({ total: 4, saved: 2, inProgress: 1, completed: 1 });
  });

  it("is empty for a student with no progress rows", () => {
    expect(summarizeLearning([])).toEqual({ total: 0, saved: 0, inProgress: 0, completed: 0 });
  });
});

describe("summarizeAssessments", () => {
  it("counts COMPLETED attempts, passes, and verified skills; keeps the latest", () => {
    const latest = attempt({ passed: true, skill_verified: true });
    const s = summarizeAssessments([
      latest,
      attempt({ passed: false, skill_verified: false }),
      attempt({ status: "IN_PROGRESS", passed: null }),
    ]);
    expect(s.completed).toBe(2);
    expect(s.passed).toBe(1);
    expect(s.skillsVerified).toBe(1);
    expect(s.latest).toBe(latest);
  });

  it("is empty for a student with no attempts", () => {
    expect(summarizeAssessments([])).toEqual({
      completed: 0,
      passed: 0,
      skillsVerified: 0,
      latest: null,
    });
  });
});

describe("toReadinessDisplay", () => {
  it("surfaces the canonical engine's readiness_percentage verbatim in JOB_ROLE mode", () => {
    const analysis = {
      mode: "JOB_ROLE",
      job_role: { id: "r", name: "Backend Developer", description: null, category: null, is_active: true, created_at: "", updated_at: "" },
      readiness_percentage: 43,
      summary: { matched: 2, needs_improvement: 1, missing: 3, unverified: 0 },
      skills: [],
      recommendations: [],
    } satisfies SkillGapJobRoleAnalysis;
    expect(toReadinessDisplay(analysis)).toEqual({
      mode: "JOB_ROLE",
      roleName: "Backend Developer",
      readinessPercentage: 43,
      matched: 2,
      needsImprovement: 1,
      missing: 3,
    });
  });

  it("returns honest counts (no percentage) in PERSONAL mode when no target role is set", () => {
    const analysis = {
      mode: "PERSONAL",
      counts: {
        total_active_skills: 5,
        verified_skills: 2,
        unverified_skills: 3,
        beginner_skills: 1,
        intermediate_skills: 2,
        advanced_skills: 2,
        expert_skills: 0,
      },
      progressable_skills: [],
      recommendations: [],
      prerequisite_gaps: [],
    } satisfies SkillGapPersonalAnalysis;
    const d = toReadinessDisplay(analysis);
    expect(d).toEqual({ mode: "PERSONAL", totalSkills: 5, verifiedSkills: 2 });
    expect(d).not.toHaveProperty("readinessPercentage");
  });
});
