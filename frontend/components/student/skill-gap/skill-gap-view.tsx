"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, RefreshCw, Target, TrendingUp } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Progress, ProgressTrack, ProgressIndicator } from "@/components/ui/progress";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { getSkillGap, listCareerRoles } from "@/lib/student/career-roles";
import type { AlignmentStatus, CareerRole, SkillGap } from "@/types/career-role";

/** GET /api/v1/career-roles + GET /api/v1/career-roles/{id}/skill-gap via
 * the FastAPI bridge (Phase 1L) -- every number rendered here comes from
 * the real backend, computed from the student's own real completed
 * assessment history. Nothing in this component is mocked or
 * hard-coded. */
export function SkillGapView() {
  const [rolesState, setRolesState] = useState<
    | { status: "loading" }
    | { status: "error"; error: ApiError }
    | { status: "ready"; roles: CareerRole[] }
  >({ status: "loading" });
  const [rolesReloadKey, setRolesReloadKey] = useState(0);

  const [selectedRoleId, setSelectedRoleId] = useState<string | null>(null);
  const [gapState, setGapState] = useState<
    | { status: "idle" }
    | { status: "loading" }
    | { status: "error"; error: ApiError }
    | { status: "ready"; gap: SkillGap }
  >({ status: "idle" });

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { career_roles } = await listCareerRoles();
        if (cancelled) return;
        setRolesState({ status: "ready", roles: career_roles });
      } catch (err) {
        if (cancelled) return;
        setRolesState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load career roles."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [rolesReloadKey]);

  // The transition to "loading" happens in handleSelectRole (a real user
  // event handler) below, not here -- setting state synchronously inside
  // an effect body is the react-hooks/set-state-in-effect anti-pattern
  // this codebase has hit before (see docs/PROJECT_CONTEXT.md §16). This
  // effect only performs the fetch itself, which is a legitimate
  // external-system synchronization.
  useEffect(() => {
    if (!selectedRoleId) return;
    let cancelled = false;
    async function load() {
      try {
        const gap = await getSkillGap(selectedRoleId!);
        if (cancelled) return;
        setGapState({ status: "ready", gap });
      } catch (err) {
        if (cancelled) return;
        setGapState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your skill gap."),
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [selectedRoleId]);

  const roleItems = useMemo(() => {
    if (rolesState.status !== "ready") return {};
    return Object.fromEntries(rolesState.roles.map((role) => [role.id, role.title]));
  }, [rolesState]);

  function handleSelectRole(roleId: string | null) {
    if (!roleId) return;
    setSelectedRoleId(roleId);
    setGapState({ status: "loading" });
  }

  return (
    <div className="flex flex-col gap-6">
      <RoleSelector
        rolesState={rolesState}
        roleItems={roleItems}
        selectedRoleId={selectedRoleId}
        onSelect={handleSelectRole}
        onRetry={() => {
          setRolesState({ status: "loading" });
          setRolesReloadKey((k) => k + 1);
        }}
      />

      {selectedRoleId && <SkillGapResult gapState={gapState} />}
    </div>
  );
}

function RoleSelector({
  rolesState,
  roleItems,
  selectedRoleId,
  onSelect,
  onRetry,
}: {
  rolesState: { status: "loading" } | { status: "error"; error: ApiError } | { status: "ready"; roles: CareerRole[] };
  roleItems: Record<string, string>;
  selectedRoleId: string | null;
  onSelect: (id: string | null) => void;
  onRetry: () => void;
}) {
  if (rolesState.status === "loading") {
    return (
      <div aria-busy="true" aria-label="Loading career roles" className="h-9 w-64 animate-pulse rounded-lg bg-muted" />
    );
  }

  if (rolesState.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load career roles.</p>
            <p className="text-sm text-muted-foreground">{rolesState.error.message}</p>
          </div>
          <Button variant="outline" size="sm" onClick={onRetry}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  if (rolesState.roles.length === 0) {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-2 py-8 text-center text-muted-foreground">
          <Target className="size-8" />
          <p className="font-medium text-foreground">No career roles available right now</p>
          <p className="text-sm">Check back later — new roles are added periodically.</p>
        </CardContent>
      </Card>
    );
  }

  return (
    <div className="max-w-sm space-y-1.5">
      <label htmlFor="career-role-select" className="text-sm font-medium">
        Career role
      </label>
      <Select value={selectedRoleId ?? undefined} onValueChange={onSelect} items={roleItems}>
        <SelectTrigger id="career-role-select" className="w-full">
          <SelectValue placeholder="Choose a career role" />
        </SelectTrigger>
        <SelectContent>
          {rolesState.roles.map((role) => (
            <SelectItem key={role.id} value={role.id}>
              {role.title}
            </SelectItem>
          ))}
        </SelectContent>
      </Select>
    </div>
  );
}

/** Exported separately from SkillGapView so it can be tested directly
 * with a controlled gapState -- see this component's own test file for
 * why: the role-selection Select is a headless (@base-ui/react) popup
 * with no existing jsdom-interaction precedent anywhere in this
 * codebase, and driving it through a real click-open-portal-click-option
 * sequence in tests was found to hang indefinitely under jsdom (no
 * ResizeObserver/PointerEvent polyfills are configured in
 * vitest.setup.ts). Testing this component's actual rendering logic
 * directly is more reliable than chasing that down, and is still a real
 * test of observable behavior, not an implementation detail. */
export function SkillGapResult({
  gapState,
}: {
  gapState:
    | { status: "idle" }
    | { status: "loading" }
    | { status: "error"; error: ApiError }
    | { status: "ready"; gap: SkillGap };
}) {
  if (gapState.status === "idle") return null;

  if (gapState.status === "loading") {
    return (
      <Card className="animate-pulse" aria-busy="true" aria-label="Loading skill gap">
        <CardHeader>
          <div className="h-5 w-1/3 rounded bg-muted" />
        </CardHeader>
        <CardContent>
          <div className="h-3 w-full rounded bg-muted" />
        </CardContent>
      </Card>
    );
  }

  if (gapState.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-8 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <div>
            <p className="font-medium">Could not load your skill gap.</p>
            <p className="text-sm text-muted-foreground">{gapState.error.message}</p>
          </div>
        </CardContent>
      </Card>
    );
  }

  const { gap } = gapState;
  const strong = gap.skills.filter((s) => s.status === "STRONG");
  const gaps = gap.skills.filter((s) => s.status === "GAP");
  const notAssessed = gap.skills.filter((s) => s.status === "NOT_ASSESSED");
  const overallScore = Number(gap.overall_score);
  const hasAnyEvidence = notAssessed.length < gap.skills.length;

  return (
    <div className="flex flex-col gap-4">
      <Card>
        <CardHeader>
          <div className="flex flex-wrap items-center gap-1.5">
            {gap.career_role.category && <Badge variant="secondary">{gap.career_role.category}</Badge>}
          </div>
          <CardTitle className="text-lg">{gap.career_role.title}</CardTitle>
          {gap.career_role.description && (
            <p className="text-sm text-muted-foreground">{gap.career_role.description}</p>
          )}
        </CardHeader>
        <CardContent className="space-y-2">
          <div className="flex items-center justify-between text-sm">
            <span className="flex items-center gap-1.5 font-medium">
              <TrendingUp className="size-4" /> Overall alignment
            </span>
            <span className="font-semibold tabular-nums">{overallScore.toFixed(0)}%</span>
          </div>
          <Progress value={overallScore}>
            <ProgressTrack>
              <ProgressIndicator />
            </ProgressTrack>
          </Progress>
        </CardContent>
      </Card>

      {!hasAnyEvidence && (
        <Card className="border-dashed">
          <CardContent className="py-4 text-sm text-muted-foreground">
            Complete an assessment to build your skill profile — the requirements for this role are
            shown below either way.
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Skill comparison</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Skill</TableHead>
                <TableHead className="text-right">You</TableHead>
                <TableHead className="text-right">Required</TableHead>
                <TableHead className="text-right">Gap</TableHead>
                <TableHead>Status</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {gap.skills.map((skill) => (
                <TableRow key={skill.skill_id}>
                  <TableCell className="font-medium">{skill.skill_name}</TableCell>
                  <TableCell className="text-right tabular-nums">
                    {skill.status === "NOT_ASSESSED" ? "—" : Number(skill.student_score).toFixed(0)}
                  </TableCell>
                  <TableCell className="text-right tabular-nums">{Number(skill.required_level).toFixed(0)}</TableCell>
                  <TableCell className="text-right tabular-nums">{Number(skill.gap).toFixed(0)}</TableCell>
                  <TableCell>
                    <StatusBadge status={skill.status} />
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      <div className="grid gap-3 sm:grid-cols-3">
        <SummaryCard label="Strong skills" count={strong.length} variant="strong" />
        <SummaryCard label="Skill gaps" count={gaps.length} variant="gap" />
        <SummaryCard label="Not assessed" count={notAssessed.length} variant="not-assessed" />
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: AlignmentStatus }) {
  if (status === "STRONG") return <Badge className="bg-emerald-600 text-white hover:bg-emerald-600">Strong</Badge>;
  if (status === "GAP") return <Badge variant="destructive">Gap</Badge>;
  return <Badge variant="outline">Not assessed</Badge>;
}

function SummaryCard({
  label,
  count,
  variant,
}: {
  label: string;
  count: number;
  variant: "strong" | "gap" | "not-assessed";
}) {
  const color =
    variant === "strong"
      ? "text-emerald-600"
      : variant === "gap"
        ? "text-destructive"
        : "text-muted-foreground";
  return (
    <Card>
      <CardContent className="py-4">
        <p className={`text-2xl font-semibold tabular-nums ${color}`}>{count}</p>
        <p className="text-sm text-muted-foreground">{label}</p>
      </CardContent>
    </Card>
  );
}
