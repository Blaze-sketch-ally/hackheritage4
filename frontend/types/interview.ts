// Mirrors the `interviews` table
// (database/migrations/030_industry_interviews.sql) and
// backend/app/schemas/interview.py. Keep all three in sync.
//
// An interview always hangs off an existing `applications` row. Its
// `industry_id` / `student_id` are server-derived from that application
// (never client-supplied), and — exactly like an application response —
// the candidate is only ever exposed as `student_id` (a uuid), never a
// name/email/profile.
//
// Lifecycle: SCHEDULED -> COMPLETED / CANCELLED. Rescheduling is an edit
// of a still-SCHEDULED interview, not a separate status.

import type { OpportunityType } from "@/types/application";

export const INTERVIEW_MODES = ["ONLINE", "PHONE", "ONSITE"] as const;
export type InterviewMode = (typeof INTERVIEW_MODES)[number];

export const INTERVIEW_MODE_LABELS: Record<InterviewMode, string> = {
  ONLINE: "Online",
  PHONE: "Phone",
  ONSITE: "On-site",
};

/** The label for the single `location` field changes by mode (the DB
 * stores a URL for ONLINE, an address for ONSITE, a number for PHONE). */
export const INTERVIEW_LOCATION_LABELS: Record<InterviewMode, string> = {
  ONLINE: "Meeting link",
  PHONE: "Phone number",
  ONSITE: "Address",
};

export const INTERVIEW_LOCATION_PLACEHOLDERS: Record<InterviewMode, string> = {
  ONLINE: "https://meet.example.com/…",
  PHONE: "+91 98765 43210",
  ONSITE: "Office address / room",
};

export const INTERVIEW_STATUSES = ["SCHEDULED", "COMPLETED", "CANCELLED"] as const;
export type InterviewStatus = (typeof INTERVIEW_STATUSES)[number];

export const INTERVIEW_STATUS_LABELS: Record<InterviewStatus, string> = {
  SCHEDULED: "Scheduled",
  COMPLETED: "Completed",
  CANCELLED: "Cancelled",
};

export interface InterviewOpportunity {
  id: string;
  title: string;
  /** The posting's own lifecycle status (DRAFT/PUBLISHED/CLOSED/ARCHIVED). */
  status: string;
}

export interface Interview {
  id: string;
  application_id: string;
  industry_id: string;
  student_id: string;
  /** ISO-8601 UTC instant. Render in the viewer's locale. */
  scheduled_at: string;
  duration_minutes: number;
  mode: InterviewMode;
  location: string | null;
  notes: string | null;
  status: InterviewStatus;
  created_at: string | null;
  updated_at: string | null;
  opportunity: InterviewOpportunity | null;
  opportunity_type: OpportunityType | null;
}

/** POST body — always created as SCHEDULED. No `industry_id`/`student_id`
 * (derived server-side from `application_id`), no `status`. */
export interface InterviewCreate {
  application_id: string;
  scheduled_at: string;
  duration_minutes: number;
  mode: InterviewMode;
  location?: string | null;
  notes?: string | null;
}

/** PATCH body — partial reschedule/edit, SCHEDULED-only. */
export interface InterviewUpdate {
  scheduled_at?: string;
  duration_minutes?: number;
  mode?: InterviewMode;
  location?: string | null;
  notes?: string | null;
}

export const DURATION_OPTIONS = [15, 30, 45, 60, 90, 120] as const;
