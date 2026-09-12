"""Controlled, read-only data-access tools for future AI agents (Phase 2).

Every function in this package takes an already-built, user-scoped
Supabase client (app.core.security.build_user_client) and a student_id --
exactly the same signature convention every existing app.services module
already uses. No function here ever calls get_supabase() (service_role)
directly; where an underlying service legitimately needs service_role for
one narrow, already-existing operation, that stays inside that service,
never duplicated here.

`student_id` is never read from anywhere but the authenticated caller's
own id (current_user.id) -- see app.api.ai's /context route, the only
caller of these tools in Phase 2. RLS remains the real access-control
boundary for every read, matching every other module in this codebase;
passing a different student's id through these functions does not widen
access, because the client is still scoped to the caller's own token.

These are plain Python functions -- no LangChain/LangGraph tool
decorators, no agent framework. That is a deliberate Phase 2 boundary,
not an oversight (see the Phase 2 report).

Nothing in this package mutates data: no write, no insert, no update, no
delete anywhere. Skill verification, assessment scoring, applications,
and match scores stay exclusively owned by the existing deterministic
services this package only reads from.
"""
