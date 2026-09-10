import { api } from "@/lib/api";
import type {
  SkillGapDetail,
  SkillGapListParams,
  SkillGapListResponse,
} from "@/types/institution-skill-gap";

/**
 * Talks to the Institution Skill Gap Analysis API
 * (backend/app/api/institution.py — /api/v1/institution/skill-gaps...).
 * Same request pattern as lib/institution/{placements,students}.ts: the
 * frontend never sends an institution id — the backend derives ownership
 * from the caller's token — and never re-aggregates or re-scores what the
 * backend returns.
 */

const BASE = "/api/v1/institution/skill-gaps";

export function getSkillGapApplications(params: SkillGapListParams = {}): Promise<SkillGapListResponse> {
  const query = new URLSearchParams();
  for (const [key, value] of Object.entries(params)) {
    if (value !== undefined && value !== null && value !== "") {
      query.set(key, String(value));
    }
  }
  const qs = query.toString();
  return api.get(`${BASE}${qs ? `?${qs}` : ""}`);
}

export function getSkillGapDetail(applicationId: string): Promise<SkillGapDetail> {
  return api.get(`${BASE}/${applicationId}`);
}
