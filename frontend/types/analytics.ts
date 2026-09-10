// Mirrors backend/app/schemas/analytics.py (IndustryAnalyticsResponse).
// Every metric is a live aggregate of the authenticated Industry
// account's OWN records — there is no analytics table.
//
// Historical scope: the database records only each row's creation date
// (and applications' apply date). It does NOT record when a status
// changed, so `timeline` is strictly "records created per month" and
// there is no stage-conversion-over-time metric. `historical_note`
// carries this caveat in the payload itself.

import type { ApplicationStatus } from "@/types/application";

export interface AnalyticsKpis {
  opportunities_total: number;
  opportunities_published: number;
  applications_total: number;
  shortlisted: number;
  interviews_total: number;
  interviews_upcoming: number;
  selected: number;
  collaborations_total: number;
  collaborations_active: number;
}

export interface OpportunityTypeBreakdown {
  opportunity_type: string;
  total: number;
  published: number;
}

export interface StatusCount {
  status: string;
  count: number;
}

export interface InterviewMetrics {
  total: number;
  scheduled: number;
  completed: number;
  cancelled: number;
  upcoming: number;
}

export interface TopOpportunity {
  id: string;
  title: string;
  opportunity_type: string;
  application_count: number;
}

export interface TimePoint {
  /** "YYYY-MM" */
  period: string;
  opportunities_created: number;
  applications_received: number;
}

export interface IndustryAnalytics {
  generated_at: string;
  kpis: AnalyticsKpis;
  funnel_counts: Record<ApplicationStatus, number>;
  funnel_total: number;
  application_status_distribution: StatusCount[];
  opportunity_breakdown: OpportunityTypeBreakdown[];
  interview_metrics: InterviewMetrics;
  top_opportunities: TopOpportunity[];
  timeline: TimePoint[];
  historical_note: string;
  interviews_available: boolean;
}

export const OPPORTUNITY_TYPE_LABELS: Record<string, string> = {
  INTERNSHIP: "Internships",
  JOB: "Jobs",
  PROJECT: "Projects",
  TRAINING: "Training",
  WORKSHOP: "Workshops",
  MENTORSHIP: "Mentorship",
  UNKNOWN: "Other",
};

/** One-line definition for every metric shown on the dashboard, so each
 * number is self-explanatory (spec: "Every displayed metric must have a
 * clear definition"). */
export const METRIC_DEFINITIONS = {
  opportunities:
    "Every internship, job, project, training, workshop and mentorship posting on your account, in any status.",
  published: "Postings currently PUBLISHED and visible to students.",
  applications: "Every application ever submitted to one of your internship or job postings.",
  shortlisted: "Applications currently at the Shortlisted stage.",
  interviews: "Interview records you have created (scheduled, completed or cancelled).",
  upcomingInterviews: "Scheduled interviews whose date/time has not yet passed.",
  selected: "Applications you have marked Selected.",
  collaborations: "Collaboration proposals you have created, in any lifecycle state.",
  activeCollaborations: "Collaborations currently ACTIVE.",
  funnel:
    "Where your applications sit right now across the recruitment pipeline. This is a current snapshot, not movement over time.",
  statusDistribution: "Count of your applications in each status, including exits (rejected/withdrawn).",
  breakdown: "How many postings you have per module, and how many of each are published.",
  interviewMetrics: "Your interview records grouped by status, plus how many are still upcoming.",
  topOpportunities: "Your postings ranked by how many applications they have received.",
  timeline:
    "Postings created and applications received per month, over the last 6 months. Based on creation dates only.",
} as const;
