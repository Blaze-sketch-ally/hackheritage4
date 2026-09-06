import { api } from "@/lib/api";
import type {
  EventDetail,
  EventListResponse,
  EventOverviewResponse,
  InstitutionEventCreate,
  InstitutionEventUpdate,
} from "@/types/institution-event";

export interface EventListQuery {
  search?: string;
  event_type?: string | null;
  status?: string | null;
  mode?: string | null;
  industry_id?: string | null;
}

/** Talks to backend/app/api/institution.py, GET /api/v1/institution/events. */
export function getInstitutionEvents(query: EventListQuery = {}): Promise<EventListResponse> {
  const params = new URLSearchParams();
  if (query.search) params.set("search", query.search);
  if (query.event_type) params.set("event_type", query.event_type);
  if (query.status) params.set("status", query.status);
  if (query.mode) params.set("mode", query.mode);
  if (query.industry_id) params.set("industry_id", query.industry_id);
  const qs = params.toString();
  return api.get(`/api/v1/institution/events${qs ? `?${qs}` : ""}`);
}

export function getInstitutionEvent(id: string): Promise<EventDetail> {
  return api.get(`/api/v1/institution/events/${id}`);
}

export function getInstitutionEventOverview(): Promise<EventOverviewResponse> {
  return api.get("/api/v1/institution/events/overview");
}

export function createInstitutionEvent(body: InstitutionEventCreate): Promise<EventDetail> {
  return api.post("/api/v1/institution/events", body);
}

export function updateInstitutionEvent(id: string, body: InstitutionEventUpdate): Promise<EventDetail> {
  return api.put(`/api/v1/institution/events/${id}`, body);
}

export function updateInstitutionEventStatus(id: string, status: string): Promise<EventDetail> {
  return api.patch(`/api/v1/institution/events/${id}/status`, { status });
}
