"""Tools: the student's own portfolio (projects, certifications,
achievements).

A thin wrapper around the EXISTING student_portfolio_service.get_portfolio
-- the same read-only aggregate GET /api/v1/student/portfolio already
returns. Evidence only: no proficiency/verification signal, matching
that service's own schema docstring (a portfolio item never touches
student_skills or assessment verification).
"""

from supabase import Client

from app.ai.schemas.student_context import PortfolioSection
from app.schemas.student_portfolio import (
    AchievementResponse,
    CertificationResponse,
    ProjectResponse,
)
from app.services import student_portfolio_service


def get_student_portfolio(client: Client, student_id: str) -> PortfolioSection:
    """The caller's own portfolio. Empty lists for a student who hasn't
    added anything yet -- not an error."""
    portfolio = student_portfolio_service.get_portfolio(client, student_id)
    return PortfolioSection(
        projects=[ProjectResponse(**row) for row in portfolio["projects"]],
        certifications=[CertificationResponse(**row) for row in portfolio["certifications"]],
        achievements=[AchievementResponse(**row) for row in portfolio["achievements"]],
    )
