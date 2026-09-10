import { api } from "@/lib/api";
import type {
  AvailableJobOption,
  DriveApplicantsResponse,
  DriveStatus,
  DriveStudentsResponse,
  PlacementDriveDetail,
  PlacementDriveFields,
  PlacementDriveListParams,
  PlacementDriveListResponse,
  PlacementDriveUpdateFields,
  PlacementOverviewResponse,
} from "@/types/institution-placement";

/**
 * Talks to the Institution Placement Drive Management API
 * (backend/app/api/institution.py — /api/v1/institution/placements...).
 * Same request pattern as lib/institution/{dashboard,students,departments}.ts:
 * the frontend never sends an institution id — the backend derives
 * ownership from the caller's token — and never re-aggregates or
 * re-scopes what the backend returns.
 */

const BASE = "/api/v1/institution/placements";

export function getAvailablePlacementJobs(search?: string): Promise<{ jobs: AvailableJobOption[] }> {
  const qs = search ? `?search=${encodeURIComponent(search)}` : "";
  return api.get(`${BASE}/available-jobs${qs}`);
}

export function getPlacementOverview(): Promise<PlacementOverviewResponse> {
  return api.get(`${BASE}/overview`);
}

export function getPlacementDrives(params: PlacementDriveListParams = {}): Promise<PlacementDriveListResponse> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  const qs = query.toString();
  return api.get(`${BASE}${qs ? `?${qs}` : ""}`);
}

export function createPlacementDrive(fields: PlacementDriveFields): Promise<PlacementDriveDetail> {
  return api.post(BASE, fields);
}

export function getPlacementDrive(driveId: string): Promise<PlacementDriveDetail> {
  return api.get(`${BASE}/${driveId}`);
}

export function updatePlacementDrive(
  driveId: string,
  fields: PlacementDriveUpdateFields,
): Promise<PlacementDriveDetail> {
  return api.put(`${BASE}/${driveId}`, fields);
}

export function updatePlacementDriveStatus(driveId: string, driveStatus: DriveStatus): Promise<PlacementDriveDetail> {
  return api.patch(`${BASE}/${driveId}/status`, { status: driveStatus });
}

export function getPlacementDriveStudents(driveId: string): Promise<DriveStudentsResponse> {
  return api.get(`${BASE}/${driveId}/students`);
}

export function getPlacementDriveApplicants(driveId: string): Promise<DriveApplicantsResponse> {
  return api.get(`${BASE}/${driveId}/applications`);
}
