"""Pydantic schemas for the STUDENT side of mentorship discovery.

This is a thin, read-only *adapter* over the one canonical mentorship
entity in this architecture -- `industry_mentorship`
(database/migrations/025_industry_mentorship.sql). There is no
`mentorship`/`mentors` table and none is introduced: a student-facing
"mentorship opportunity" is just a normalized view of one PUBLISHED
`industry_mentorship` row.

`industry_mentorship` already carries the RLS policy
"Authenticated users can view published mentorship opportunities"
(select, `status = 'PUBLISHED'`), so a STUDENT caller can already read
those rows through build_user_client(); this adapter relies on that
rather than widening any policy.

There is NO mentorship request / pairing / enrollment model anywhere in
the repository. 025_industry_mentorship.sql states plainly that the
Industry-side posting is "Model C" and "a future Student/Collaboration
phase owns any request/pairing workflow" -- but a request table with no
Industry-side responder API or UI would be a dead-end half-feature, so
S5 does NOT introduce one. This adapter exposes `requests_available:
false` and the student frontend shows a truthful "requests aren't
available yet" state. Mentorship is strictly read-only for students;
nothing here can create, update, or delete an `industry_mentorship` row.

The student-facing id is the raw `industry_mentorship` UUID -- there is
only one source table, so no prefixing is needed.
"""

from pydantic import BaseModel

# database/migrations/025_industry_mentorship.sql -- industry_mentorship.work_mode CHECK.
STUDENT_MENTORSHIP_WORK_MODES = ("ONSITE", "REMOTE", "HYBRID")


class StudentMentorshipOrganizer(BaseModel):
    """Company display info for the offering Industry account, read from
    `industry_profiles` (RLS: "Authenticated users can view industry
    profiles"). `company_name` can be null -- an Industry account can
    publish a mentorship opportunity before filling in its company
    profile -- and no `profiles` column (full_name, email, ...) is ever
    exposed here; a student has no RLS path to it."""

    id: str
    company_name: str | None = None
    industry_sector: str | None = None
    logo_url: str | None = None


class StudentMentorshipSummary(BaseModel):
    """One PUBLISHED industry mentorship opportunity, normalized for the
    browse list."""

    id: str
    title: str
    description: str
    location: str
    work_mode: str  # ONSITE / REMOTE / HYBRID -- the mentorship mode
    duration_months: int
    capacity: int
    start_date: str | None = None
    application_deadline: str | None = None
    organizer: StudentMentorshipOrganizer | None = None
    created_at: str | None = None


class StudentMentorshipDetail(StudentMentorshipSummary):
    """One PUBLISHED industry mentorship opportunity, normalized for the
    detail page."""

    eligibility_criteria: str | None = None
    # Always False in this phase: there is no canonical mentorship request
    # backend. Surfaced as a real field so the frontend renders an honest
    # state from the API rather than a hard-coded assumption.
    requests_available: bool = False


class StudentMentorshipListResponse(BaseModel):
    mentorship_opportunities: list[StudentMentorshipSummary]
