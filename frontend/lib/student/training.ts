import { api } from "@/lib/api";
import type { StudentTraining, StudentTrainingListResponse } from "@/types/student-training";
import type {
  TrainingApplication,
  TrainingApplicationListResponse,
} from "@/types/training-application";

/**
 * Talks to OUR Student Training API
 * (backend/app/api/student_trainings.py, /api/v1/student/trainings).
 */

export function listTrainings(params?: { search?: string }): Promise<StudentTrainingListResponse> {
  const query = new URLSearchParams();
  if (params?.search?.trim()) query.set("search", params.search.trim());
  const qs = query.toString();
  return api.get(`/api/v1/student/trainings${qs ? `?${qs}` : ""}`);
}

export function getTraining(id: string): Promise<StudentTraining> {
  return api.get(`/api/v1/student/trainings/${encodeURIComponent(id)}`);
}

export function applyToTraining(id: string): Promise<TrainingApplication> {
  return api.post(`/api/v1/student/trainings/${encodeURIComponent(id)}/applications`, {});
}

export function listMyTrainingApplications(): Promise<TrainingApplicationListResponse> {
  return api.get("/api/v1/student/training-applications");
}

export function withdrawTrainingApplication(applicationId: string): Promise<TrainingApplication> {
  return api.post(
    `/api/v1/student/training-applications/${encodeURIComponent(applicationId)}/withdraw`,
  );
}
