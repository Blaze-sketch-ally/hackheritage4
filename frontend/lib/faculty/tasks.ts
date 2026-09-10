import { api } from "@/lib/api";
import type { FacultyTasks } from "@/types/faculty-tasks";

/**
 * Thin 1:1 wrapper over GET /api/v1/faculty/tasks -- same shape as
 * lib/faculty/profile.ts. require_faculty + the backend's own capability
 * checks are the real enforcement; this module holds no privileged
 * credentials and does no filtering of its own.
 */
export function getFacultyTasks(): Promise<FacultyTasks> {
  return api.get("/api/v1/faculty/tasks");
}
