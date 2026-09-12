"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  ArrowRight,
  ArrowUpRight,
  BookOpen,
  Briefcase,
  ClipboardCheck,
  ListChecks,
  Sparkles,
  Target,
  type LucideIcon,
} from "lucide-react";
import type { ReactNode } from "react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/common/error-state";
import { YouTubeLearningCard } from "@/components/student/learning/youtube-learning-card";
import { describeNextAction, getCareerGuidance } from "@/lib/student/career-guidance";
import type {
  AgentStatus,
  AssessmentRecommendationItem,
  CareerGuidanceResponse,
  LearningRecommendationItem,
  NextAction,
  OpportunityRecommendationItem,
  PrioritySkill,
} from "@/types/career-guidance";

type LoadState =
  | { status: "loading" }
  | { status: "error" }
  | { status: "ready"; data: CareerGuidanceResponse };

const BAND_LABEL: Record<string, string> = {
  STRONG: "Strong skill match",
  GOOD: "Good skill match",
  PARTIAL: "Partial skill match",
  LOW: "Some overlap",
};

/**
 * The Phase 6 AI Career Orchestrator's synthesized view -- the "where am
 * I now / what should I do next" summary for this Career page. Every
 * name, score, band, status, and code here was attached server-side from
 * the same canonical engines (skill_gap_service / match_service /
 * learning_recommendation_service) that the deterministic sections below
 * already trust -- this panel never renders unrestricted model text, and
 * a failure here never blocks the deterministic Skill Gap workspace
 * below it. Fetched independently of it for exactly that reason.
 */
export function CareerGuidancePanel() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getCareerGuidance()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch(() => {
        if (!cancelled) setState({ status: "error" });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  if (state.status === "loading") return <CareerGuidanceSkeleton />;

  if (state.status === "error") {
    return (
      <ErrorState
        message="Couldn't load your AI career guidance."
        onRetry={() => {
          setState({ status: "loading" });
          setReloadKey((k) => k + 1);
        }}
      />
    );
  }

  return <CareerGuidanceReady data={state.data} />;
}

function CareerGuidanceReady({ data }: { data: CareerGuidanceResponse }) {
  const {
    career_summary,
    priority_skills,
    learning_recommendations,
    youtube_videos,
    opportunity_recommendations,
    assessment_recommendations,
    next_actions,
    meta,
    disclaimer,
  } = data;

  const degraded = [
    meta.agents_used.course_agent.available ? null : meta.agents_used.course_agent,
    meta.agents_used.opportunity_agent.available ? null : meta.agents_used.opportunity_agent,
    meta.agents_used.career_advisor.available ? null : meta.agents_used.career_advisor,
  ].filter((s): s is AgentStatus => s !== null);

  const hasNothingYet = !career_summary.target_role && priority_skills.length === 0;

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2 text-base">
            <Sparkles className="size-4 text-violet-600 dark:text-violet-400" aria-hidden="true" />
            AI Career Guidance
          </CardTitle>
        </CardHeader>
        <CardContent className="space-y-3">
          {hasNothingYet ? (
            <p className="text-sm text-muted-foreground">
              Add skills or pick a target role below to get a personalized readiness summary.
            </p>
          ) : (
            <>
              <div className="flex flex-wrap items-center justify-between gap-2">
                <p className="font-medium">{career_summary.target_role ?? "Personal development"}</p>
                {career_summary.readiness_score !== null && (
                  <Badge variant="outline">{career_summary.readiness_score}% ready</Badge>
                )}
              </div>
              {career_summary.headline && (
                <p className="text-sm text-muted-foreground">{career_summary.headline}</p>
              )}
            </>
          )}

          {degraded.map((s, i) => (
            <p key={i} className="flex items-start gap-1.5 text-xs text-muted-foreground">
              <AlertTriangle className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              {s.detail ?? "One part of your AI guidance is temporarily unavailable."}
            </p>
          ))}
        </CardContent>
      </Card>

      {next_actions.length > 0 && (
        <Section icon={ListChecks} title="Next Actions">
          <div className="flex flex-col gap-2">
            {next_actions.map((action) => (
              <NextActionRow key={`${action.type}-${action.entity_id}-${action.order}`} action={action} />
            ))}
          </div>
        </Section>
      )}

      {priority_skills.length > 0 && (
        <Section icon={Target} title="Priority Skills">
          <div className="grid gap-2 sm:grid-cols-2">
            {priority_skills.slice(0, 6).map((skill) => (
              <PrioritySkillCard key={skill.skill_id} skill={skill} />
            ))}
          </div>
        </Section>
      )}

      {(learning_recommendations.length > 0 || youtube_videos.length > 0) && (
        <Section icon={BookOpen} title="Recommended Learning">
          {learning_recommendations.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2">
              {learning_recommendations.slice(0, 6).map((item) => (
                <LearningCard key={item.course.candidate_id} item={item} />
              ))}
            </div>
          )}
          {youtube_videos.length > 0 && (
            <div className="grid gap-3 sm:grid-cols-2">
              {youtube_videos.slice(0, 6).map((item) => (
                <YouTubeLearningCard
                  key={item.video.video_id}
                  video={item.video}
                  skillName={item.for_skill_name}
                  reason={item.reason}
                />
              ))}
            </div>
          )}
        </Section>
      )}

      {opportunity_recommendations.length > 0 && (
        <Section icon={Briefcase} title="Recommended Opportunities">
          <div className="grid gap-3 sm:grid-cols-2">
            {opportunity_recommendations.slice(0, 4).map((item) => (
              <OpportunityCard key={item.opportunity.id} item={item} />
            ))}
          </div>
        </Section>
      )}

      {assessment_recommendations.length > 0 && (
        <Section icon={ClipboardCheck} title="Assessments to Prioritize">
          <div className="grid gap-2 sm:grid-cols-2">
            {assessment_recommendations.slice(0, 6).map((item) => (
              <AssessmentCard key={item.skill_id} item={item} />
            ))}
          </div>
        </Section>
      )}

      <p className="text-xs text-muted-foreground">{disclaimer}</p>
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  children,
}: {
  icon: LucideIcon;
  title: string;
  children: ReactNode;
}) {
  return (
    <div className="space-y-3">
      <h2 className="flex items-center gap-2 text-base font-semibold">
        <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
        {title}
      </h2>
      {children}
    </div>
  );
}

function NextActionRow({ action }: { action: NextAction }) {
  const href =
    action.entity_type === "OPPORTUNITY"
      ? undefined // opportunity id prefix/route is resolved on the opportunity card itself
      : action.entity_type === "COURSE"
        ? undefined // course links go to the provider URL on its own card
        : action.entity_type === "ASSESSMENT" || action.entity_type === "SKILL"
          ? "/student/skill-gap"
          : undefined;

  const label = describeNextAction(action);
  const content = (
    <>
      <Badge variant="secondary" className="shrink-0">
        {action.order}
      </Badge>
      <span className="min-w-0 flex-1 truncate text-sm font-medium">{label}</span>
      {href && <ArrowRight className="size-3.5 shrink-0 text-muted-foreground" aria-hidden="true" />}
    </>
  );

  if (href) {
    return (
      <Link
        href={href}
        className="flex items-center gap-2 rounded-lg border px-3 py-2 transition-colors hover:bg-muted"
      >
        {content}
      </Link>
    );
  }

  return <div className="flex items-center gap-2 rounded-lg border px-3 py-2">{content}</div>;
}

function PrioritySkillCard({ skill }: { skill: PrioritySkill }) {
  return (
    <Card className={skill.highlighted_by_advisor ? "border-violet-400/50" : undefined}>
      <CardContent className="space-y-1.5 py-3">
        <div className="flex items-start justify-between gap-2">
          <p className="text-sm font-medium">{skill.skill_name}</p>
          {skill.canonical_priority && (
            <Badge variant="outline" className={priorityClass(skill.canonical_priority)}>
              {skill.canonical_priority}
            </Badge>
          )}
        </div>
        <p className="text-xs text-muted-foreground">{skill.reason}</p>
        <p className="text-xs font-medium text-foreground">{skill.suggested_action}</p>
      </CardContent>
    </Card>
  );
}

function LearningCard({ item }: { item: LearningRecommendationItem }) {
  const { course } = item;
  // Every one of these is server-owned CourseCandidate metadata (internal
  // catalog or a configured external provider, e.g. Microsoft Learn) --
  // only ever rendered when the source actually returned it, never inferred.
  const badges = [
    course.level,
    course.duration_text,
    course.price_text,
    course.rating !== null ? `${course.rating}★` : null,
    course.certificate_available ? "Certificate" : null,
  ].filter((v): v is string => Boolean(v));
  return (
    <Card className={item.highlighted_by_advisor ? "border-violet-400/50" : undefined}>
      <CardContent className="space-y-1.5 py-3">
        <p className="text-sm font-medium">{course.title}</p>
        {course.provider && <p className="text-xs text-muted-foreground">{course.provider}</p>}
        {item.for_skill_name && (
          <p className="text-xs text-muted-foreground">For: {item.for_skill_name}</p>
        )}
        {badges.length > 0 && (
          <div className="flex flex-wrap gap-1">
            {badges.map((b) => (
              <Badge key={b} variant="outline" className="text-[10px]">
                {b}
              </Badge>
            ))}
          </div>
        )}
        <p className="text-xs text-muted-foreground">{item.reason}</p>
        <Button
          size="sm"
          variant="outline"
          className="w-full"
          render={<Link href={course.url} target="_blank" rel="noopener noreferrer" />}
          nativeButton={false}
        >
          View course <ArrowUpRight className="size-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}

function OpportunityCard({ item }: { item: OpportunityRecommendationItem }) {
  const { opportunity, match } = item;
  const segment = opportunity.source_type === "INTERNSHIP" ? "internships" : "jobs";
  return (
    <Card className={item.highlighted_by_advisor ? "border-violet-400/50" : undefined}>
      <CardContent className="space-y-1.5 py-3">
        <div className="flex flex-wrap items-center gap-1.5">
          <Badge variant="secondary">{opportunity.source_type === "INTERNSHIP" ? "Internship" : "Job"}</Badge>
          {opportunity.location && <Badge variant="outline">{opportunity.location}</Badge>}
        </div>
        <p className="text-sm font-medium">{opportunity.title}</p>
        <p className="text-xs text-muted-foreground">
          <span className="font-medium text-foreground">
            Matches {match.matched_count} of {match.required_count} skills
          </span>{" "}
          — {BAND_LABEL[match.recommendation] ?? match.recommendation}
        </p>
        <p className="text-xs text-muted-foreground">{item.reason}</p>
        <Button
          size="sm"
          variant="outline"
          className="w-full"
          render={<Link href={`/student/${segment}/${opportunity.id}`} />}
          nativeButton={false}
        >
          View {segment === "internships" ? "internship" : "job"} <ArrowRight className="size-3.5" />
        </Button>
      </CardContent>
    </Card>
  );
}

const ASSESSMENT_CTA: Record<
  AssessmentRecommendationItem["action"],
  { label: string; linkable: boolean }
> = {
  ADD_SKILL_THEN_ASSESS: { label: "Add skill, then take assessment", linkable: true },
  TAKE_ASSESSMENT: { label: "Take assessment", linkable: true },
  ALREADY_VERIFIED: { label: "Already verified", linkable: false },
  NO_ASSESSMENT_AVAILABLE: { label: "No assessment available yet", linkable: false },
};

function AssessmentCard({ item }: { item: AssessmentRecommendationItem }) {
  const cta = ASSESSMENT_CTA[item.action];
  return (
    <Card className={item.highlighted_by_advisor ? "border-violet-400/50" : undefined}>
      <CardContent className="space-y-1.5 py-3">
        <p className="text-sm font-medium">{item.skill_name}</p>
        <p className="text-xs text-muted-foreground">{item.note}</p>
        {cta.linkable ? (
          <Button
            size="sm"
            variant="outline"
            className="w-full"
            render={<Link href="/student/skill-gap" />}
            nativeButton={false}
          >
            {cta.label}
          </Button>
        ) : (
          <Badge variant="outline" className="w-fit">
            {cta.label}
          </Badge>
        )}
      </CardContent>
    </Card>
  );
}

function priorityClass(p: string): string {
  return (
    {
      HIGH: "border-destructive/30 bg-destructive/10 text-destructive",
      MEDIUM: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
      LOW: "border-border text-muted-foreground",
    }[p] ?? "border-border text-muted-foreground"
  );
}

function CareerGuidanceSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-label="Loading AI career guidance" aria-busy="true">
      {[0, 1].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2 py-6">
            <div className="h-4 w-1/3 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
            <div className="h-3 w-2/3 rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
