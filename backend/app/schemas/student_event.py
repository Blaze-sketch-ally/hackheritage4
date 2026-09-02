"""Pydantic schemas for the STUDENT side of event discovery.

This is a thin, read-only *adapter* over the one real event-style table in
this architecture -- `industry_workshops`
(database/migrations/024_industry_workshops.sql). There is no `events`
table and none is introduced: a student-facing "event" is just a
normalized view of one PUBLISHED industry workshop.

`industry_workshops` already carries the RLS policy
"Authenticated users can view published workshops"
(select, `status = 'PUBLISHED'`), so a STUDENT caller can already read
those rows through build_user_client(); this adapter relies on that
rather than widening any policy.

There is NO registration model anywhere in the repository
(024_industry_workshops.sql explicitly has "no application/registration
table"), so this adapter exposes none and invents none -- the student
frontend shows a truthful "registration isn't available yet" state.
Events are strictly read-only for students; nothing here can create,
update, or delete a workshop row.

The student-facing event id is the raw workshop UUID -- there is only one
source table, so no prefixing is needed (unlike student_opportunity's
internship_/job_ split).
"""

from pydantic import BaseModel

# database/migrations/024_industry_workshops.sql -- industry_workshops.work_mode CHECK.
StudentEventWorkMode = ("ONSITE", "REMOTE", "HYBRID")


class StudentEventOrganizer(BaseModel):
    """Company display info for the organising Industry account, read from
    `industry_profiles` (RLS: "Authenticated users can view industry
    profiles"). `company_name` can be null -- an Industry account can
    publish a workshop before filling in its company profile -- and no
    `profiles` column (full_name, email, ...) is ever exposed here; a
    student has no RLS path to it."""

    id: str
    company_name: str | None = None
    industry_sector: str | None = None
    logo_url: str | None = None


class StudentEventSummary(BaseModel):
    """One PUBLISHED industry workshop, normalized for the browse list."""

    id: str
    title: str
    description: str
    location: str | None = None
    work_mode: str | None = None  # ONSITE / REMOTE / HYBRID -- the "online indicator"
    start_date: str | None = None
    application_deadline: str | None = None
    duration_days: int | None = None
    organizer: StudentEventOrganizer | None = None
    created_at: str | None = None


class StudentEventDetail(StudentEventSummary):
    """One PUBLISHED industry workshop, normalized for the detail page."""

    capacity: int | None = None
    eligibility_criteria: str | None = None
    # Always False in this phase: there is no canonical registration
    # backend. Surfaced as a real field so the frontend renders an honest
    # state from the API rather than a hard-coded assumption.
    registration_available: bool = False


class StudentEventListResponse(BaseModel):
    events: list[StudentEventSummary]
