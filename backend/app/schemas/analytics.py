"""Pydantic schemas for Industry Analytics.

Every metric here is computed live from the caller's OWN records
(applications, interviews, the six opportunity modules, collaborations) --
scoped by industry_id, through a user-scoped RLS client. There is no
analytics table and no stored aggregate.

Historical scope is deliberately limited to what the data can honestly
support: the schema records each row's `created_at` (and applications'
`applied_at`), so "records created over time" is real. It does NOT record
WHEN a status changed -- only the current status plus a single
`updated_at` -- so point-in-time funnel movement (when a candidate was
shortlisted, selected, ...) and any stage-conversion trend over time are
not available. `IndustryAnalyticsResponse.historical_note` states this in
the payload itself.
"""

from pydantic import BaseModel


class AnalyticsKpis(BaseModel):
    """Current-state headline counts. Every value is a count of the
    caller's own rows as they stand right now."""

    opportunities_total: int
    opportunities_published: int
    applications_total: int
    shortlisted: int
    interviews_total: int
    interviews_upcoming: int
    selected: int
    collaborations_total: int
    collaborations_active: int


class OpportunityTypeBreakdown(BaseModel):
    """One opportunity module: how many the caller has, and how many are
    live (PUBLISHED)."""

    opportunity_type: str
    total: int
    published: int


class StatusCount(BaseModel):
    status: str
    count: int


class InterviewMetrics(BaseModel):
    total: int
    scheduled: int
    completed: int
    cancelled: int
    upcoming: int


class TopOpportunity(BaseModel):
    """A posting ranked by how many applications it has received."""

    id: str
    title: str
    opportunity_type: str
    application_count: int


class TimePoint(BaseModel):
    """One calendar month. `opportunities_created` counts postings created
    that month across all six modules; `applications_received` counts
    applications whose `applied_at` falls in that month. Both are
    creation-date facts -- never inferred status history."""

    period: str  # "YYYY-MM"
    opportunities_created: int
    applications_received: int


class IndustryAnalyticsResponse(BaseModel):
    generated_at: str
    kpis: AnalyticsKpis
    # Per-status application counts (every status present, 0 when none) --
    # identical shape to GET /api/v1/applications/summary so the frontend
    # recruitment funnel renders it directly.
    funnel_counts: dict[str, int]
    funnel_total: int
    application_status_distribution: list[StatusCount]
    opportunity_breakdown: list[OpportunityTypeBreakdown]
    interview_metrics: InterviewMetrics
    top_opportunities: list[TopOpportunity]
    timeline: list[TimePoint]
    historical_note: str
    # True only when the interviews table (migration 030) is present.
    # False -> interview_metrics is all zeros and the note explains why.
    interviews_available: bool
