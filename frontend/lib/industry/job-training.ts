import { api } from "@/lib/api";
import type {
  JobAssignmentInput,
  JobProgramBundle,
  JobProgramItemInput,
  JobProgramItemType,
  JobProgramMetaInput,
  JobProgramModuleInput,
  SkillRequirement,
} from "@/types/job-training-program";

/**
 * Talks to the Industry Job Training program-authoring API
 * (backend/app/api/job_training_programs.py,
 * /api/v1/jobs/{job_id}/training-program). Components call these functions,
 * never `api.*` directly. Ownership is never sent -- the backend derives
 * the industry from the caller's token and RLS (public.owns_job_program) is
 * the real boundary. Mirrors lib/industry/internship-program.ts, minus the
 * submission/review surface (Job Training has no submission system).
 *
 * Every call returns the full authoring bundle, so the caller can replace
 * its state wholesale after each mutation instead of patching it.
 */

function base(jobId: string): string {
  return `/api/v1/jobs/${encodeURIComponent(jobId)}/training-program`;
}

export function getJobTrainingProgram(jobId: string): Promise<JobProgramBundle> {
  return api.get(base(jobId));
}

export function createJobTrainingProgram(
  jobId: string,
  data: JobProgramMetaInput,
): Promise<JobProgramBundle> {
  return api.post(base(jobId), data);
}

export function updateJobTrainingProgram(
  jobId: string,
  data: JobProgramMetaInput,
): Promise<JobProgramBundle> {
  return api.put(base(jobId), data);
}

export function publishJobTrainingProgram(jobId: string): Promise<JobProgramBundle> {
  return api.post(`${base(jobId)}/publish`);
}

export function unpublishJobTrainingProgram(jobId: string): Promise<JobProgramBundle> {
  return api.post(`${base(jobId)}/unpublish`);
}

export function setJobTrainingProgramSkills(
  jobId: string,
  skills: { skill_id: string; requirement: SkillRequirement }[],
): Promise<JobProgramBundle> {
  return api.put(`${base(jobId)}/skills`, { skills });
}

export function createJobProgramModule(
  jobId: string,
  data: JobProgramModuleInput,
): Promise<JobProgramBundle> {
  return api.post(`${base(jobId)}/modules`, data);
}

export function updateJobProgramModule(
  jobId: string,
  moduleId: string,
  data: JobProgramModuleInput,
): Promise<JobProgramBundle> {
  return api.put(`${base(jobId)}/modules/${encodeURIComponent(moduleId)}`, data);
}

export function reorderJobProgramModules(
  jobId: string,
  orderedIds: string[],
): Promise<JobProgramBundle> {
  return api.post(`${base(jobId)}/modules/reorder`, { ordered_ids: orderedIds });
}

export function createJobProgramItem(
  jobId: string,
  moduleId: string,
  data: JobProgramItemInput & { item_type: JobProgramItemType; title: string },
): Promise<JobProgramBundle> {
  return api.post(`${base(jobId)}/modules/${encodeURIComponent(moduleId)}/items`, data);
}

export function updateJobProgramItem(
  jobId: string,
  moduleId: string,
  itemId: string,
  data: JobProgramItemInput,
): Promise<JobProgramBundle> {
  return api.put(
    `${base(jobId)}/modules/${encodeURIComponent(moduleId)}/items/${encodeURIComponent(itemId)}`,
    data,
  );
}

export function reorderJobProgramItems(
  jobId: string,
  moduleId: string,
  orderedIds: string[],
): Promise<JobProgramBundle> {
  return api.post(
    `${base(jobId)}/modules/${encodeURIComponent(moduleId)}/items/reorder`,
    { ordered_ids: orderedIds },
  );
}

// No delete -- the schema has no DELETE policy; hiding (is_published=false)
// is the remove-from-students mechanism, same as the internship analog.

export function createJobProgramAssignment(
  jobId: string,
  moduleId: string,
  data: JobAssignmentInput & { title: string },
): Promise<JobProgramBundle> {
  return api.post(`${base(jobId)}/modules/${encodeURIComponent(moduleId)}/assignments`, data);
}

export function updateJobProgramAssignment(
  jobId: string,
  moduleId: string,
  assignmentId: string,
  data: JobAssignmentInput,
): Promise<JobProgramBundle> {
  return api.put(
    `${base(jobId)}/modules/${encodeURIComponent(moduleId)}/assignments/${encodeURIComponent(assignmentId)}`,
    data,
  );
}

export function reorderJobProgramAssignments(
  jobId: string,
  moduleId: string,
  orderedIds: string[],
): Promise<JobProgramBundle> {
  return api.post(
    `${base(jobId)}/modules/${encodeURIComponent(moduleId)}/assignments/reorder`,
    { ordered_ids: orderedIds },
  );
}
