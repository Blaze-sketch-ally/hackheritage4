"""AI specialist agents. Each agent is a thin orchestrator over Phase 1
(app.ai.client) and Phase 2 (app.ai.context / app.ai.tools) -- never a
second data-access layer, never a replacement for the deterministic
services those tools already wrap. See skill_gap_agent.py for the first
one.
"""
