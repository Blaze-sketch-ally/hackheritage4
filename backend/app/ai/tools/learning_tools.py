"""Tools: the student's own learning progress.

A thin wrapper around the EXISTING student_learning_service.list_my_progress
-- the same rows GET /api/v1/student/learning/progress already returns.
Learning progress is never treated as skill evidence here either -- see
that service's own module docstring (033_learning_resources.sql).
"""

from supabase import Client

from app.schemas.student_learning import StudentLearningProgressItem
from app.services import student_learning_service


def get_learning_progress(client: Client, student_id: str) -> list[StudentLearningProgressItem]:
    """The caller's own learning progress, newest activity first. Empty
    list for a student who hasn't saved/started anything yet -- not an
    error."""
    rows = student_learning_service.list_my_progress(client, student_id)
    return [StudentLearningProgressItem(**row) for row in rows]
