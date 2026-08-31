"""Idempotent, re-runnable generator that populates the assessment catalog
(assessments + assessment_blueprint_rules + assessment_questions +
assessment_question_options + assessment_question_answers) from the
static content in assessment_catalog_data.py.

NOT a migration -- creates no tables/columns/functions/policies. Uses
only the existing schema from 004_assessments.sql and
015_assessment_verification.sql, exactly as those migrations defined it.

NO LLM. NO runtime question generation. All question content is
pre-authored and imported from assessment_catalog_data.py.

Requires backend/.env (SUPABASE_URL + SUPABASE_SERVICE_ROLE_KEY) -- run it
from a machine that already has the backend's Python environment set up:

    cd backend
    .venv/Scripts/python.exe ../database/seed/generate_assessment_catalog.py

Idempotency (safe to re-run):
  - Skills are looked up by NAME (skills.name), never a hardcoded UUID --
    per-project convention (see skills_fixed.sql's own header).
  - An assessment is looked up by the (skill_id, difficulty) pair; if one
    already exists for that pair, it is REUSED (not duplicated), and its
    id is used for the blueprint rule / question checks below. This
    directly enforces "exactly one assessment per skill+difficulty" at
    the seed level -- the schema itself doesn't need a new constraint for
    this, since 004_assessments.sql's own comment already documents that
    "multiple assessments per skill are expected" is a possibility the
    schema allows but this seed does not exercise.
  - A blueprint rule is looked up by (assessment_id, difficulty) -- the
    same unique constraint 015_assessment_verification.sql already
    defines -- and only inserted if absent.
  - Questions are only inserted for an assessment the FIRST time it has
    zero existing questions. Re-running this script against an
    already-seeded assessment does not add duplicate questions.

To extend to more skills: add a new entry to SKILLS in
assessment_catalog_data.py (skill name must exactly match an existing
skills.name row) and re-run this script -- only the new skill's rows will
be created; everything already seeded is left untouched.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "backend"))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from assessment_catalog_data import SKILLS

from app.database.supabase import get_supabase

DIFFICULTIES = ["Beginner", "Intermediate", "Advanced"]


def main() -> None:
    client = get_supabase()

    summary = {
        "skills_processed": 0,
        "skills_not_found": [],
        "assessments_created": 0,
        "assessments_reused": 0,
        "blueprint_rules_created": 0,
        "blueprint_rules_existing": 0,
        "questions_created": 0,
        "options_created": 0,
        "answer_keys_created": 0,
        "assessments_already_had_questions": 0,
    }

    for skill_name, by_difficulty in SKILLS.items():
        skill_row = (
            client.table("skills").select("id").eq("name", skill_name).maybe_single().execute()
        )
        if skill_row is None:
            print(f"SKIP: skill '{skill_name}' not found in the catalog (skills.name mismatch?)")
            summary["skills_not_found"].append(skill_name)
            continue
        skill_id = skill_row.data["id"]
        summary["skills_processed"] += 1

        for difficulty in DIFFICULTIES:
            config = by_difficulty[difficulty]
            questions = config["questions"]
            select_count = config["select_count"]
            pool_size = len(questions)
            if pool_size <= select_count:
                raise ValueError(
                    f"{skill_name} {difficulty}: pool size ({pool_size}) must exceed "
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

            print(f"  seeded {len(questions)} questions for {skill_name} {difficulty}")

    print()
    print("=== SUMMARY ===")
    for key, value in summary.items():
        print(f"{key}: {value}")


if __name__ == "__main__":
    main()
