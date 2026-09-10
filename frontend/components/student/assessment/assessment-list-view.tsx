"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { AlertCircle, Clock, GraduationCap, ListChecks, RefreshCw } from "lucide-react";
import { Card, CardContent, CardFooter, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api";
import { listAssessments } from "@/lib/student/assessment";
import { createClient } from "@/lib/supabase/client";
import { fetchStudentSkills, type StudentSkill } from "@/lib/student/skills";
import type { Assessment, Difficulty } from "@/types/assessment";

/** The order assessments are listed within a skill -- mirrors the
 * 'Beginner'/'Intermediate'/'Advanced'/'Expert' scale shared by
 * assessments.difficulty and student_skills.proficiency_level. Not a
 * hardcoded skill list -- a hardcoded *difficulty* ordering, which the DB
 * CHECK constraint itself fixes. */
const DIFFICULTY_ORDER: Difficulty[] = ["Beginner", "Intermediate", "Advanced", "Expert"];

type SkillGroup = {
  skillId: string;
  skillName: string;
  categoryName: string | null;
  assessments: Assessment[];
};

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; groups: SkillGroup[]; hasSkills: boolean };

/** The Assessments page is fully data-driven:
 *
 *  1. the student's selected skills come from the existing
 *     `student_skills` source of truth (fetchStudentSkills), and
 *  2. the assessments come from GET /api/v1/assessments, which the
 *     backend has ALREADY filtered to exactly those selected skills
 *     (assessment_service.list_assessments_for_student) -- the client
 *     never sends a skill id/name and cannot widen the result.
 *
 * The page then groups those assessments under each selected skill and
 * lists that skill's Beginner/Intermediate/Advanced assessments. A skill
 * with no assessment in the database shows an explicit "not available
 * yet" note rather than a fabricated entry. There is no hardcoded list of
 * skills anywhere in this file. */
export function AssessmentListView({ studentId }: { studentId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [{ assessments }, studentSkills] = await Promise.all([
          listAssessments(),
          fetchStudentSkills(createClient(), studentId),
        ]);
        if (cancelled) return;
        setState({
          status: "ready",
          groups: buildGroups(studentSkills, assessments),
          hasSkills: studentSkills.length > 0,
        });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load assessments."),
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey, studentId]);

  if (state.status === "loading") {
    return <AssessmentListSkeleton />;
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">
              {state.error.status === 401
                ? "Your session has expired. Please sign in again."
                : "Could not load assessments."}
            </p>
            <p className="text-sm text-muted-foreground">{state.error.message}</p>
          </div>
          {state.error.status !== 401 && (
            <Button
              variant="outline"
              size="sm"
              onClick={() => {
                setState({ status: "loading" });
                setReloadKey((k) => k + 1);
              }}
            >
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          )}
        </CardContent>
      </Card>
    );
  }

  const { groups, hasSkills } = state;

  if (!hasSkills) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-10 text-center text-muted-foreground">
          <GraduationCap className="size-8" />
          <p className="font-medium text-foreground">No skills selected yet</p>
          <p className="text-sm">
            Assessments are shown for the skills on your profile. Add a skill to see its
            Beginner, Intermediate, and Advanced assessments here.
          </p>
          <Button size="sm" className="mt-2" render={<Link href="/student/skills" />} nativeButton={false}>
            Go to My Skills
          </Button>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="flex flex-col gap-8">
      {groups.map((group) => (
        <section key={group.skillId} className="flex flex-col gap-3">
          <div className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5">
            <h2 className="text-base font-semibold">{group.skillName}</h2>
            {group.categoryName && (
              <span className="text-xs text-muted-foreground">{group.categoryName}</span>
            )}
          </div>

          {group.assessments.length === 0 ? (
            <p className="text-sm text-muted-foreground">
              No assessment available yet for this skill.
            </p>
          ) : (
            <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3">
              {group.assessments.map((assessment) => (
                <AssessmentListCard key={assessment.id} assessment={assessment} />
              ))}
            </div>
          )}
        </section>
      ))}
    </div>
  );
}

/** Groups the (already skill-filtered) assessments under each selected
 * skill, in the skill's own alphabetical order, with each skill's
 * assessments ordered Beginner -> Intermediate -> Advanced -> Expert.
 * A selected skill with no assessment still gets a group (empty
 * `assessments`) so the page can say so explicitly. */
function buildGroups(studentSkills: StudentSkill[], assessments: Assessment[]): SkillGroup[] {
  const bySkill = new Map<string, Assessment[]>();
  for (const assessment of assessments) {
    const list = bySkill.get(assessment.skill_id) ?? [];
    list.push(assessment);
    bySkill.set(assessment.skill_id, list);
  }

  return studentSkills
    .map((studentSkill) => {
      const list = (bySkill.get(studentSkill.skill_id) ?? [])
        .slice()
        .sort(
          (a, b) =>
            DIFFICULTY_ORDER.indexOf(a.difficulty) - DIFFICULTY_ORDER.indexOf(b.difficulty),
        );
      return {
        skillId: studentSkill.skill_id,
        skillName: studentSkill.skill.name,
        categoryName: studentSkill.skill.category?.name ?? null,
        assessments: list,
      };
    })
    .sort((a, b) => a.skillName.localeCompare(b.skillName));
}

function AssessmentListCard({ assessment }: { assessment: Assessment }) {
  return (
    <Card className="flex flex-col">
      <CardHeader>
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="outline">{assessment.difficulty}</Badge>
        </div>
        <CardTitle className="text-base">{assessment.title}</CardTitle>
      </CardHeader>
      <CardContent className="flex-1 text-sm text-muted-foreground">
        {assessment.description && <p className="mb-3">{assessment.description}</p>}
        <div className="flex flex-wrap gap-x-4 gap-y-1.5">
          {assessment.duration_minutes != null && (
            <span className="flex items-center gap-1">
              <Clock className="size-3.5" /> {assessment.duration_minutes} min
            </span>
          )}
          {assessment.question_count != null && (
            <span className="flex items-center gap-1">
              <ListChecks className="size-3.5" /> {assessment.question_count} questions
            </span>
          )}
        </div>
      </CardContent>
      <CardFooter>
        <Button
          className="w-full"
          render={<Link href={`/student/assessment/${assessment.id}`} />}
          nativeButton={false}
        >
          Start assessment
        </Button>
      </CardFooter>
    </Card>
  );
}

function AssessmentListSkeleton() {
  return (
    <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-3" aria-busy="true" aria-label="Loading assessments">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardHeader>
            <div className="h-4 w-16 rounded bg-muted" />
            <div className="mt-2 h-5 w-3/4 rounded bg-muted" />
          </CardHeader>
          <CardContent>
            <div className="h-3 w-full rounded bg-muted" />
            <div className="mt-2 h-3 w-2/3 rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
