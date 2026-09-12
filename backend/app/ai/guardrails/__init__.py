"""Deterministic, post-LLM validation ("grounding") for AI agent output.

Nothing here calls Groq or Supabase. Each module is a pure function of
(LLM output, canonical data) -> a sanitized/rejected result -- see
skill_gap.py for the Skill Gap Agent's guardrail.
"""
