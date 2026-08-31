"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { GraduationCap } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { EmptyState } from "@/components/common/empty-state";
import { RecommendationsPanel } from "@/components/student/skill-gap/recommendations-panel";
import type { SkillGapPersonalAnalysis } from "@/types/skill-gap";

/** The no-target-role view: a summary of the student's own active
 * skills, which have a next-level assessment available, and skill-graph
 * recommendations for what to learn next -- no career-readiness
 * percentage is ever shown here (there's no role to be ready for). */
export function PersonalAnalysisView({ analysis }: { analysis: SkillGapPersonalAnalysis }) {
  const router = useRouter();
  const { counts } = analysis;

  if (counts.total_active_skills === 0) {
    return (
      <EmptyState
        icon={GraduationCap}
        title="You haven't added any skills yet."
        description="Add your skills to see a personal skill analysis and recommendations."
        actionLabel="Add Skills"
        onAction={() => router.push("/student/skills")}
      />
    );
  }

  const stats = [
    { label: "Total Skills", value: counts.total_active_skills },
    { label: "Verified Skills", value: counts.verified_skills },
    { label: "Unverified Skills", value: counts.unverified_skills },
    { label: "Beginner", value: counts.beginner_skills },
    { label: "Intermediate", value: counts.intermediate_skills },
    { label: "Advanced", value: counts.advanced_skills },
    { label: "Expert", value: counts.expert_skills },
  ];

  return (
    <div className="space-y-6">
      <div>
        <h2 className="text-base font-semibold">Personal Skill Analysis</h2>
        <div className="mt-2 grid grid-cols-2 gap-4 sm:grid-cols-4">
          {stats.map((stat) => (
            <Card key={stat.label}>
              <CardContent className="space-y-1">
                <p className="text-sm text-muted-foreground">{stat.label}</p>
                <p className="text-2xl font-semibold tracking-tight">{stat.value}</p>
              </CardContent>
            </Card>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <h2 className="text-base font-semibold">Skills You Should Develop Next</h2>
        <RecommendationsPanel recommendations={analysis.recommendations} />
      </div>

      <div className="space-y-2">
        <h2 className="text-base font-semibold">Recommended Assessments</h2>
        {analysis.progressable_skills.length === 0 ? (
          <EmptyState title="No recommended assessments available yet." />
        ) : (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3">
            {analysis.progressable_skills.map((skill) => (
              <Card key={skill.skill_id}>
                <CardContent className="space-y-2">
                  <p className="text-sm font-medium">{skill.skill_name}</p>
                  <p className="text-xs text-muted-foreground">
                    {skill.current_level} → {skill.next_level}
                  </p>
                  {skill.assessment_available && skill.assessment_id ? (
                    <Button
                      size="sm"
                      className="w-full"
                      render={<Link href={`/student/assessment/${skill.assessment_id}`} />}
                      nativeButton={false}
                    >
                      Take Assessment
                    </Button>
                  ) : (
                    <p className="text-xs text-muted-foreground">Assessment not available yet.</p>
                  )}
                </CardContent>
              </Card>
            ))}
          </div>
        )}
      </div>

      {analysis.prerequisite_gaps.length > 0 ? (
        <div className="space-y-2">
          <h2 className="text-base font-semibold">Prerequisites You&apos;ll Need First</h2>
          <Card>
            <CardContent className="space-y-1.5 text-sm">
              {analysis.prerequisite_gaps.map((gap) => (
                <p key={`${gap.skill_id}-${gap.required_for_skill_id}`} className="text-muted-foreground">
                  <span className="font-medium text-foreground">{gap.skill_name}</span> is a prerequisite for{" "}
                  {gap.required_for_skill_name}.
                </p>
              ))}
            </CardContent>
          </Card>
        </div>
      ) : null}
    </div>
  );
}
