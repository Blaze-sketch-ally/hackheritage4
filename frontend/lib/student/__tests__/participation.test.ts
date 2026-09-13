import { describe, expect, it } from "vitest";
import { canSubmitAssignment } from "@/lib/student/participation";
import type { ReviewStatus, SubmissionResponse } from "@/types/participation";

function submission(reviewStatus: ReviewStatus | null, submissionStatus: SubmissionResponse["status"] = "SUBMITTED"): SubmissionResponse {
  return {
    id: "sub-1",
    workspace_id: "ws-1",
    assignment_id: "a-1",
    assignment_title: "Assignment",
    attempt_number: 1,
    submission_text: "text",
    submission_url: null,
    submitted_at: "2026-01-01T00:00:00Z",
    status: submissionStatus,
    created_at: "2026-01-01T00:00:00Z",
    latest_review:
      reviewStatus === null
        ? null
        : {
            id: "rev-1",
            submission_id: "sub-1",
            reviewer_id: "industry-1",
            score: null,
            feedback: null,
            status: reviewStatus,
            reviewed_at: "2026-01-02T00:00:00Z",
            created_at: "2026-01-02T00:00:00Z",
          },
  };
}

describe("canSubmitAssignment", () => {
  it("allows the first submission when none exists yet", () => {
    expect(canSubmitAssignment(undefined)).toBe(true);
  });

  it("blocks a duplicate submission while pending review (SUBMITTED, no review yet)", () => {
    expect(canSubmitAssignment(submission(null, "SUBMITTED"))).toBe(false);
  });

  it("blocks a duplicate submission while UNDER_REVIEW", () => {
    expect(canSubmitAssignment(submission(null, "UNDER_REVIEW"))).toBe(false);
  });

  it("allows resubmission when the latest review is NEEDS_REVISION", () => {
    expect(canSubmitAssignment(submission("NEEDS_REVISION"))).toBe(true);
  });

  it("blocks resubmission once ACCEPTED", () => {
    expect(canSubmitAssignment(submission("ACCEPTED"))).toBe(false);
  });

  it("blocks resubmission for the neutral REVIEWED verdict, same as ACCEPTED", () => {
    expect(canSubmitAssignment(submission("REVIEWED"))).toBe(false);
  });
});
