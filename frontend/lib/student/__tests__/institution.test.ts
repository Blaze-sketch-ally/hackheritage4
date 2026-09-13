import { describe, expect, it } from "vitest";
import { resolveStudentInstitutionLinkState } from "@/lib/student/institution";
import type { InstitutionLinkRequest } from "@/types/institution-link";
import type { StudentInstitutionResponse } from "@/types/student-institution";

const EMPTY_WORKSPACE: StudentInstitutionResponse = {
  linked: false,
  institution: null,
  profile: null,
  kpis: { placement_drives: 0, internships: 0, events: 0, active_applications: 0 },
  placement_drives: [],
  internships: [],
  events: [],
  activity: [],
  curation_note: "",
  eligibility_note: "",
  registration_note: "",
};

function request(overrides: Partial<InstitutionLinkRequest> = {}): InstitutionLinkRequest {
  return {
    id: "r1",
    student_id: "s1",
    institution_id: "inst-1",
    status: "PENDING",
    created_at: null,
    updated_at: null,
    student_name: null,
    student_username: null,
    institution_name: "ABC University",
    ...overrides,
  };
}

describe("resolveStudentInstitutionLinkState", () => {
  it("is NOT_CONNECTED with no workspace link and no requests", () => {
    expect(resolveStudentInstitutionLinkState(EMPTY_WORKSPACE, [])).toEqual({ kind: "NOT_CONNECTED" });
  });

  it("is PENDING when a live PENDING request exists", () => {
    expect(resolveStudentInstitutionLinkState(EMPTY_WORKSPACE, [request({ status: "PENDING" })])).toEqual({
      kind: "PENDING",
      institutionName: "ABC University",
    });
  });

  it("is VERIFIED when the workspace itself already reports linked", () => {
    const workspace: StudentInstitutionResponse = { ...EMPTY_WORKSPACE, linked: true };
    expect(resolveStudentInstitutionLinkState(workspace, [])).toEqual({ kind: "VERIFIED", workspace });
  });

  it("is VERIFIED_AWAITING_SYNC when the request is APPROVED but the workspace still reports linked: false (the reported bug)", () => {
    expect(resolveStudentInstitutionLinkState(EMPTY_WORKSPACE, [request({ status: "APPROVED" })])).toEqual({
      kind: "VERIFIED_AWAITING_SYNC",
      institutionName: "ABC University",
    });
  });

  it("is REJECTED when the most recent (non-live) request was REJECTED", () => {
    expect(resolveStudentInstitutionLinkState(EMPTY_WORKSPACE, [request({ status: "REJECTED" })])).toEqual({
      kind: "REJECTED",
      institutionName: "ABC University",
    });
  });

  it("is NOT_CONNECTED after a CANCELLED request (student may request again)", () => {
    expect(resolveStudentInstitutionLinkState(EMPTY_WORKSPACE, [request({ status: "CANCELLED" })])).toEqual({
      kind: "NOT_CONNECTED",
    });
  });
});
