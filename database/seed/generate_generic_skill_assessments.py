"""Idempotent, re-runnable generator that gives EVERY active catalog skill
a Beginner / Intermediate / Advanced assessment, using the skill-agnostic
template content in generic_assessment_content.py.

Companion to generate_assessment_catalog.py:
  - generate_assessment_catalog.py seeds the small set of skills that have
    a curated, domain-specific question bank (assessment_catalog_data.SKILLS).
  - THIS script seeds every OTHER active skill in the `skills` table with
    the generic template bank, so the data-driven Assessments page has
    real Beginner/Intermediate/Advanced assessments to show for any skill
    a student selects.

Run generate_assessment_catalog.py FIRST, then this one. Skills present in
assessment_catalog_data.SKILLS are skipped here (by name, case-insensitive)
so the curated content is never overwritten or duplicated.

NOT a migration -- creates no tables/columns/functions/policies. Uses only
the existing schema from 004_assessments.sql and
015_assessment_verification.sql.

NO LLM. NO runtime question generation. See generic_assessment_content.py.

Requires backend/.env (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY):

    cd backend
    .venv/Scripts/python.exe ../database/seed/generate_generic_skill_assessments.py

Idempotency (safe to re-run, and safe to run after
generate_assessment_catalog.py):
  - Skills are read live from `skills` (is_active = true); no UUIDs are
    hardcoded.
  - An assessment is looked up by (skill_id, difficulty); an existing one
    is REUSED, never duplicated -- this also means a curated assessment
    that somehow shares a (skill_id, difficulty) is left completely alone.
  - A blueprint rule is looked up by (assessment_id, difficulty) and only
    inserted if absent.
  - Questions are inserted for an assessment ONLY the first time it has
    zero questions. Re-running never adds duplicate questions/options/
    answer keys.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from assessment_catalog_data import SKILLS as CURATED_SKILLS
from generic_assessment_content import DIFFICULTIES, DIFFICULTY_CONFIG, build_questions

from app.database.supabase import get_supabase


def main() -> None:
    client = get_supabase()
    curated_names = {name.strip().lower() for name in CURATED_SKILLS}

    skills = (
        client.table("skills")
        .select("id, name")
        .eq("is_active", True)
        .order("name")
        .execute()
        .data
        or []
    )

    summary = {
        "skills_seen": len(skills),
        "skills_skipped_curated": 0,
        "skills_processed": 0,
        "assessments_created": 0,
        "assessments_reused": 0,
        "blueprint_rules_created": 0,
        "blueprint_rules_existing": 0,
        "questions_created": 0,
        "options_created": 0,
        "answer_keys_created": 0,
        "assessments_already_had_questions": 0,
    }

    for skill in skills:
        skill_name = skill["name"]
        skill_id = skill["id"]

        if skill_name.strip().lower() in curated_names:
            summary["skills_skipped_curated"] += 1
            print(f"SKIP (curated): {skill_name}")
            continue

        summary["skills_processed"] += 1

        for difficulty in DIFFICULTIES:
            config = DIFFICULTY_CONFIG[difficulty]
            select_count = config["select_count"]
            questions = build_questions(skill_name, difficulty)
            pool_size = len(questions)
            if pool_size <= select_count:
                raise ValueError(
                    f"{skill_name} {difficulty}: generic pool size ({pool_size}) must exceed "
                    f"select_count ({select_count}) for randomization to be meaningful."
                )

            existing = (
                client.table("assessments")
                .select("id")
                .eq("skill_id", skill_id)
                .eq("difficulty", difficulty)
                .maybe_single()
                .execute()
            )
            if existing is not None:
                assessment_id = existing.data["id"]
                summary["assessments_reused"] += 1
                print(f"REUSE assessment: {skill_name} {difficulty} ({assessment_id})")
            else:
                created = (
                    client.table("assessments")
                    .insert(
                        {
                            "skill_id": skill_id,
                            "title": f"{skill_name} {difficulty} Assessment",
                            "description": (
                                f"A {difficulty.lower()}-level assessment covering {skill_name}."
                            ),
                            "difficulty": difficulty,
                            "duration_minutes": config["duration_minutes"],
                            "question_count": select_count,
                            "passing_percentage": config["passing_percentage"],
                            "is_active": True,
                        }
                    )
                    .execute()
                    .data[0]
                )
                assessment_id = created["id"]
                summary["assessments_created"] += 1
                print(f"CREATE assessment: {skill_name} {difficulty} ({assessment_id})")

            existing_rule = (
                client.table("assessment_blueprint_rules")
                .select("id")
                .eq("assessment_id", assessment_id)
                .eq("difficulty", difficulty)
                .maybe_single()
                .execute()
            )
            if existing_rule is None:
                client.table("assessment_blueprint_rules").insert(
                    {
                        "assessment_id": assessment_id,
                        "difficulty": difficulty,
                        "question_count": select_count,
                    }
                ).execute()
                summary["blueprint_rules_created"] += 1
            else:
                summary["blueprint_rules_existing"] += 1

            existing_questions = (
                client.table("assessment_questions")
                .select("id")
                .eq("assessment_id", assessment_id)
                .limit(1)
                .execute()
            )
            if existing_questions.data:
                summary["assessments_already_had_questions"] += 1
                print(f"  questions already exist for {skill_name} {difficulty} -- skipping")
                continue

            for question_text, option_texts, correct_index, explanation in questions:
                question = (
                    client.table("assessment_questions")
                    .insert(
                        {
                            "assessment_id": assessment_id,
                            "question_text": question_text,
                            "question_type": "MCQ",
                            "scoring_method": "OBJECTIVE",
                            "difficulty": difficulty,
                            "points": 1,
                            "review_status": "APPROVED",
                            "is_active": True,
                        }
                    )
                    .execute()
                    .data[0]
                )
                summary["questions_created"] += 1

                option_ids = []
                for i, option_text in enumerate(option_texts):
                    option = (
                        client.table("assessment_question_options")
                        .insert(
                            {
                                "question_id": question["id"],
                                "option_text": option_text,
                                "display_order": i,
                            }
                        )
                        .execute()
                        .data[0]
                    )
                    option_ids.append(option["id"])
                    summary["options_created"] += 1

                client.table("assessment_question_answers").insert(
                    {
                        "question_id": question["id"],
                        "correct_option_ids": [option_ids[correct_index]],
                        "explanation": explanation,
                    }
                ).execute()
                summary["answer_keys_created"] += 1

            print(f"  seeded {len(questions)} generic questions for {skill_name} {difficulty}")

    print()
    print("=== SUMMARY ===")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
