"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  ArrowUpRight,
  Award,
  BadgeCheck,
  FolderKanban,
  Code2,
  Plus,
  Target,
  Trophy,
} from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { ErrorState } from "@/components/common/error-state";
import { ApiError } from "@/lib/api";
import { getPortfolio } from "@/lib/student/portfolio";
import { formatDateRange, formatMonthYear, type PortfolioResponse } from "@/types/student-portfolio";

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; data: PortfolioResponse };

export function PortfolioView({
  displayName,
  headline,
}: {
  displayName: string;
  headline: string | null;
}) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getPortfolio()
      .then((data) => {
        if (!cancelled) setState({ status: "ready", data });
      })
      .catch((err) => {
        if (!cancelled) {
          setState({
            status: "error",
            message: err instanceof ApiError ? err.message : "Could not load your portfolio.",
          });
        }
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  return (
    <div className="mx-auto flex max-w-4xl flex-col gap-6">
      <div>
        <h1 className="text-xl font-semibold">{displayName}</h1>
        <p className="text-sm text-muted-foreground">
          {headline || "Your portfolio — projects, certifications, achievements, and skills."}
        </p>
      </div>

      {state.status === "loading" && <PortfolioSkeleton />}

      {state.status === "error" && (
        <ErrorState
          message={state.message}
          onRetry={() => {
            setState({ status: "loading" });
            setReloadKey((k) => k + 1);
          }}
        />
      )}

      {state.status === "ready" && <PortfolioBody data={state.data} />}
    </div>
  );
}

function PortfolioBody({ data }: { data: PortfolioResponse }) {
  const empty =
    data.projects.length === 0 &&
    data.certifications.length === 0 &&
    data.achievements.length === 0 &&
    data.skills.length === 0;

  if (empty) {
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed px-6 py-12 text-center">
        <FolderKanban className="size-8 text-muted-foreground" aria-hidden="true" />
        <div className="space-y-1">
          <p className="text-sm font-medium">Your portfolio is empty</p>
          <p className="text-sm text-muted-foreground">
            Add projects, certifications, achievements, and skills to build it.
          </p>
        </div>
        <div className="flex flex-wrap justify-center gap-2 pt-1">
          <Button size="sm" render={<Link href="/student/projects" />} nativeButton={false}>
            <Plus className="size-4" /> Add a project
          </Button>
          <Button
            size="sm"
            variant="outline"
            render={<Link href="/student/certifications" />}
            nativeButton={false}
          >
            Add a certification
          </Button>
          <Button
            size="sm"
            variant="outline"
            render={<Link href="/student/achievements" />}
            nativeButton={false}
          >
            Add an achievement
          </Button>
          <Button
            size="sm"
            variant="outline"
            render={<Link href="/student/skills" />}
            nativeButton={false}
          >
            Add skills
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col gap-6">
      <Section
        icon={Target}
        title="Skills"
        count={data.skills.length}
        addHref="/student/skills"
        addLabel="Manage skills"
        emptyText="No skills added yet."
      >
        {data.skills.length > 0 && (
          <div className="flex flex-wrap gap-1.5">
            {data.skills.map((s) => (
              <Badge key={s.skill_id} variant={s.is_verified ? "default" : "outline"} className="gap-1">
                {s.is_verified && <BadgeCheck className="size-3" aria-hidden="true" />}
                {s.skill_name} · {s.proficiency_level}
              </Badge>
            ))}
          </div>
        )}
      </Section>

      <Section
        icon={FolderKanban}
        title="Projects"
        count={data.projects.length}
        addHref="/student/projects"
        addLabel="Manage projects"
        emptyText="No projects yet."
      >
        <div className="grid gap-3 sm:grid-cols-2">
          {data.projects.map((p) => {
            const range = formatDateRange(p.start_date, p.end_date, p.is_ongoing);
            return (
              <div key={p.id} className="rounded-lg border border-border/60 p-3">
                <Link
                  href={`/student/projects/${p.id}`}
                  className="text-sm font-medium hover:underline"
                >
                  {p.title}
                </Link>
                {range && <p className="text-xs text-muted-foreground">{range}</p>}
                {p.description && (
                  <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">{p.description}</p>
                )}
                {p.skills.length > 0 && (
                  <div className="mt-1.5 flex flex-wrap gap-1">
                    {p.skills.map((s) => (
                      <Badge key={s.skill_id} variant="outline" className="font-normal">
                        {s.skill_name}
                      </Badge>
                    ))}
                  </div>
                )}
                <div className="mt-1.5 flex gap-3 text-xs">
                  {p.project_url && (
                    <a
                      href={p.project_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 hover:underline"
                    >
                      <ArrowUpRight className="size-3" /> Live
                    </a>
                  )}
                  {p.repo_url && (
                    <a
                      href={p.repo_url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="flex items-center gap-1 hover:underline"
                    >
                      <Code2 className="size-3" /> Code
                    </a>
                  )}
                </div>
              </div>
            );
          })}
        </div>
      </Section>

      <Section
        icon={Award}
        title="Certifications"
        count={data.certifications.length}
        addHref="/student/certifications"
        addLabel="Manage certifications"
        emptyText="No certifications yet."
      >
        <div className="flex flex-col gap-2">
          {data.certifications.map((c) => (
            <div key={c.id} className="rounded-lg border border-border/60 p-3 text-sm">
              <p className="font-medium">{c.name}</p>
              <p className="text-xs text-muted-foreground">
                {c.issuing_organization}
                {c.issuing_organization && c.issue_date && " · "}
                {c.issue_date && `Issued ${formatMonthYear(c.issue_date)}`}
              </p>
              {c.credential_url && (
                <a
                  href={c.credential_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="mt-1 inline-flex items-center gap-1 text-xs hover:underline"
                >
                  <ArrowUpRight className="size-3" /> View credential
                </a>
              )}
            </div>
          ))}
        </div>
      </Section>

      <Section
        icon={Trophy}
        title="Achievements"
        count={data.achievements.length}
        addHref="/student/achievements"
        addLabel="Manage achievements"
        emptyText="No achievements yet."
      >
        <div className="flex flex-col gap-2">
          {data.achievements.map((a) => (
            <div key={a.id} className="rounded-lg border border-border/60 p-3 text-sm">
              <p className="font-medium">{a.title}</p>
              <p className="text-xs text-muted-foreground">
                {a.achievement_date && formatMonthYear(a.achievement_date)}
                {a.achievement_date && a.issuing_organization && " · "}
                {a.issuing_organization}
              </p>
              {a.description && (
                <p className="mt-1 text-xs text-muted-foreground">{a.description}</p>
              )}
            </div>
          ))}
        </div>
      </Section>
    </div>
  );
}

function Section({
  icon: Icon,
  title,
  count,
  addHref,
  addLabel,
  emptyText,
  children,
}: {
  icon: typeof Target;
  title: string;
  count: number;
  addHref: string;
  addLabel: string;
  emptyText: string;
  children: React.ReactNode;
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle className="flex items-center gap-2 text-base">
            <Icon className="size-4 text-muted-foreground" aria-hidden="true" />
            {title}
            <span className="text-sm font-normal text-muted-foreground">({count})</span>
          </CardTitle>
          <Button
            variant="ghost"
            size="sm"
            render={<Link href={addHref} />}
            nativeButton={false}
          >
            {addLabel}
          </Button>
        </div>
      </CardHeader>
      <CardContent>
        {count === 0 ? (
          <p className="text-sm text-muted-foreground">{emptyText}</p>
        ) : (
          children
        )}
      </CardContent>
    </Card>
  );
}

function PortfolioSkeleton() {
  return (
    <div className="flex flex-col gap-4" aria-label="Loading portfolio" aria-busy="true">
      {[0, 1, 2].map((i) => (
        <Card key={i} className="animate-pulse">
          <CardContent className="space-y-2 py-5">
            <div className="h-4 w-1/3 rounded bg-muted" />
            <div className="h-3 w-full rounded bg-muted" />
          </CardContent>
        </Card>
      ))}
    </div>
  );
}
