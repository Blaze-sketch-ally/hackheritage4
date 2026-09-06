import { api } from "@/lib/api";
import type {
  AssignmentInput,
  IndustrySubmissionDetail,
  IndustrySubmissionList,
  InternshipProgramBundle,
  ModuleInput,
  ModuleItemInput,
  ModuleItemType,
  ProgramMetaInput,
  ReviewSubmissionInput,
  SkillRequirement,
} from "@/types/internship-program";

/**
 * Talks to the Industry internship-program API
 * (backend/app/api/internship_programs.py,
 * /api/v1/internships/{internship_id}/program). Components call these
 * functions, never `api.*` directly. Ownership is never sent -- the
 * backend derives the industry from the caller's token and RLS
 * (public.owns_internship_program) is the real boundary.
 *
 * Every call returns the full authoring bundle, so the caller can replace
 * its state wholesale after each mutation instead of patching it (which
 * could diverge from the database).
 */

function base(internshipId: string): string {
  return `/api/v1/internships/${encodeURIComponent(internshipId)}/program`;
}

export function getInternshipProgram(
  internshipId: string,
): Promise<InternshipProgramBundle> {
  return api.get(base(internshipId));
}

export function createInternshipProgram(
  internshipId: string,
  data: ProgramMetaInput,
): Promise<InternshipProgramBundle> {
  return api.post(base(internshipId), data);
}

export function updateInternshipProgram(
  internshipId: string,
  data: ProgramMetaInput,
): Promise<InternshipProgramBundle> {
  return api.put(base(internshipId), data);
}

export function publishInternshipProgram(
  internshipId: string,
): Promise<InternshipProgramBundle> {
  return api.post(`${base(internshipId)}/publish`);
}

export function setInternshipProgramSkills(
  internshipId: string,
  skills: { skill_id: string; requirement: SkillRequirement }[],
): Promise<InternshipProgramBundle> {
  return api.put(`${base(internshipId)}/skills`, { skills });
}

export function createProgramModule(
  internshipId: string,
  data: ModuleInput,
): Promise<InternshipProgramBundle> {
  return api.post(`${base(internshipId)}/modules`, data);
}

export function updateProgramModule(
  internshipId: string,
  moduleId: string,
  data: ModuleInput,
): Promise<InternshipProgramBundle> {
  return api.put(`${base(internshipId)}/modules/${encodeURIComponent(moduleId)}`, data);
}

export function reorderProgramModules(
  internshipId: string,
  orderedIds: string[],
): Promise<InternshipProgramBundle> {
  return api.post(`${base(internshipId)}/modules/reorder`, { ordered_ids: orderedIds });
}

export function createModuleItem(
  internshipId: string,
  moduleId: string,
  data: ModuleItemInput & { item_type: ModuleItemType; title: string },
): Promise<InternshipProgramBundle> {
  return api.post(
    `${base(internshipId)}/modules/${encodeURIComponent(moduleId)}/items`,
    data,
  );
}

export function updateModuleItem(
  internshipId: string,
  moduleId: string,
  itemId: string,
  data: ModuleItemInput,
): Promise<InternshipProgramBundle> {
  return api.put(
    `${base(internshipId)}/modules/${encodeURIComponent(moduleId)}/items/${encodeURIComponent(itemId)}`,
    data,
  );
}

export function reorderModuleItems(
  internshipId: string,
  moduleId: string,
  orderedIds: string[],
): Promise<InternshipProgramBundle> {
  return api.post(
    `${base(internshipId)}/modules/${encodeURIComponent(moduleId)}/items/reorder`,
    { ordered_ids: orderedIds },
  );
}

// ---- Phase 5: assignments (within a module). No delete -- hide via
// is_published (037 grants no DELETE policy). ----

export function createProgramAssignment(
  internshipId: string,
  moduleId: string,
  data: AssignmentInput & { title: string },
): Promise<InternshipProgramBundle> {
  return api.post(
    `${base(internshipId)}/modules/${encodeURIComponent(moduleId)}/assignments`,
    data,
  );
}

export function updateProgramAssignment(
  internshipId: string,
  moduleId: string,
  assignmentId: string,
  data: AssignmentInput,
): Promise<InternshipProgramBundle> {
  return api.put(
    `${base(internshipId)}/modules/${encodeURIComponent(moduleId)}/assignments/${encodeURIComponent(assignmentId)}`,
    data,
  );
}

export function reorderProgramAssignments(
  internshipId: string,
  moduleId: string,
  orderedIds: string[],
): Promise<InternshipProgramBundle> {
  return api.post(
    `${base(internshipId)}/modules/${encodeURIComponent(moduleId)}/assignments/reorder`,
    { ordered_ids: orderedIds },
  );
}

// ---- Phase 5: READ-ONLY submission view. Never approves / rejects /
// comments / scores -- that is Phase 6. ----

export function listProgramSubmissions(
  internshipId: string,
  params: { assignmentId?: string; workspaceId?: string } = {},
): Promise<IndustrySubmissionList> {
  const q = new URLSearchParams();
  if (params.assignmentId) q.set("assignment_id", params.assignmentId);
  if (params.workspaceId) q.set("workspace_id", params.workspaceId);
  const suffix = q.toString() ? `?${q.toString()}` : "";
  return api.get(`${base(internshipId)}/submissions${suffix}`);
}

export function getProgramSubmission(
  internshipId: string,
  submissionId: string,
): Promise<IndustrySubmissionDetail> {
  return api.get(
    `${base(internshipId)}/submissions/${encodeURIComponent(submissionId)}`,
  );
}

// ---- Phase 6: review a submission attempt. The decision is stored in
// submission_reviews (append-only); the student's submission row is never
// rewritten. `reviewer_id` is always the authenticated industry account. ----

export function startProgramSubmissionReview(
  internshipId: string,
  submissionId: string,
): Promise<IndustrySubmissionDetail> {
  return api.post(
    `${base(internshipId)}/submissions/${encodeURIComponent(submissionId)}/review/start`,
    {},
  );
}

export function reviewProgramSubmission(
  internshipId: string,
  submissionId: string,
  data: ReviewSubmissionInput,
): Promise<IndustrySubmissionDetail> {
  return api.post(
    `${base(internshipId)}/submissions/${encodeURIComponent(submissionId)}/review`,
    data,
  );
}
