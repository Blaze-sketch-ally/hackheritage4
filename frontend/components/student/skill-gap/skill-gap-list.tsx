"use client";

import Link from "next/link";
import { CheckCircle2, Circle, TriangleAlert, XCircle } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import type { GapStatus, Priority, SkillGapItem } from "@/types/skill-gap";

const STATUS_DISPLAY: Record<GapStatus, { label: string; icon: typeof CheckCircle2; className: string }> = {
  MATCHED: {
    label: "Matched",
    icon: CheckCircle2,
    className: "border-emerald-500/30 bg-emerald-500/10 text-emerald-600 dark:text-emerald-400",
  },
  NEEDS_IMPROVEMENT: {
    label: "Needs Improvement",
    icon: TriangleAlert,
    className: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
  },
  MISSING: {
    label: "Missing",
    icon: XCircle,
    className: "border-destructive/30 bg-destructive/10 text-destructive",
  },
};

const PRIORITY_CLASSNAME: Record<Priority, string> = {
  HIGH: "border-destructive/30 bg-destructive/10 text-destructive",
  MEDIUM: "border-amber-500/30 bg-amber-500/10 text-amber-600 dark:text-amber-400",
  LOW: "border-border text-muted-foreground",
};

/** The per-required-skill breakdown table for a job-role analysis. Every
 * value comes directly from the backend's SkillGapItem -- status, gap,
 * verification, and priority are never recomputed here. */
export function SkillGapList({ skills }: { skills: SkillGapItem[] }) {
  return (
    <Card>
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>Skill</TableHead>
            <TableHead>Current → Required</TableHead>
            <TableHead>Gap</TableHead>
            <TableHead>Status</TableHead>
            <TableHead>Verification</TableHead>
            <TableHead>Importance</TableHead>
            <TableHead>Priority</TableHead>
            <TableHead>Assessment</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {skills.map((skill) => (
            <SkillGapRow key={skill.skill_id} skill={skill} />
          ))}
        </TableBody>
      </Table>
    </Card>
  );
}

function SkillGapRow({ skill }: { skill: SkillGapItem }) {
  const status = STATUS_DISPLAY[skill.status];
  const StatusIcon = status.icon;

  return (
    <TableRow>
      <TableCell className="font-medium">{skill.skill_name}</TableCell>
      <TableCell className="whitespace-nowrap">
        {skill.current_level ?? "Not Added"} → {skill.required_level}
      </TableCell>
      <TableCell>{skill.gap}</TableCell>
      <TableCell>
        <Badge variant="outline" className={status.className}>
          <StatusIcon className="size-3" aria-hidden="true" />
          {status.label}
        </Badge>
      </TableCell>
      <TableCell>
        {skill.current_level === null ? (
          <span className="text-muted-foreground">—</span>
        ) : skill.verification_status === "VERIFIED" ? (
          <span className="flex items-center gap-1 text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="size-3.5" aria-hidden="true" /> Verified
          </span>
        ) : (
          <span className="flex items-center gap-1 text-muted-foreground">
            <Circle className="size-3.5" aria-hidden="true" /> Not Verified
          </span>
        )}
      </TableCell>
      <TableCell>
        <Badge variant="secondary">{skill.importance}</Badge>
      </TableCell>
      <TableCell>
        <Badge variant="outline" className={PRIORITY_CLASSNAME[skill.priority]}>
          {skill.priority}
        </Badge>
      </TableCell>
      <TableCell>
        {skill.assessment_available && skill.assessment_id ? (
          <Button
            size="sm"
            render={<Link href={`/student/assessment/${skill.assessment_id}`} />}
            nativeButton={false}
          >
            Take Assessment
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground">Assessment not available yet.</span>
        )}
      </TableCell>
    </TableRow>
  );
}
