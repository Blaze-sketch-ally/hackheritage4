import { api } from "@/lib/api";

/**
 * Read-only access to the shared skill catalog (backend/app/api/skills.py,
 * GET /api/v1/skills). Used by the internship skill-requirements picker.
 * Industry users pick from this catalog — they cannot create new skills.
 */

export interface CatalogSkill {
  id: string;
  name: string;
  category_name: string | null;
  description: string | null;
}

export function getSkillCatalog(search?: string): Promise<{ skills: CatalogSkill[] }> {
  const qs = search?.trim() ? `?search=${encodeURIComponent(search.trim())}` : "";
  return api.get(`/api/v1/skills${qs}`);
}
