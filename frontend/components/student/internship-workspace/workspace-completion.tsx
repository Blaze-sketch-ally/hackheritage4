"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Award, CheckCircle2, Circle, ExternalLink } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent } from "@/components/ui/card";
import { ApiError } from "@/lib/api";
import { getMyWorkspaceCompletion } from "@/lib/student/internship-workspace";
import type { CompletionSummary } from "@/types/internship-completion";

function fmt(value: string | null): string {
  if (!value) return "—";
  const d = new Date(value);
  return Number.isNaN(d.getTime())
    ? value
    : d.toLocaleDateString(undefined, { year: "numeric", month: "long", day: "numeric" });
}

/** The student's own completion + certificate status
 * (GET .../internship-workspaces/{id}/completion). Requirements /
 * verification / the certificate are all computed and issued
 * server-side -- this component only displays them. */
export function WorkspaceCompletion({ workspaceId }: { workspaceId: string }) {
  const [state, setState] = useState<
    | { status: "loading" }
    | { status: "error"; message: string }
    | { status: "ready"; summary: CompletionSummary }
  >({ status: "loading" });

  useEffect(() => {
    let cancelled = false;
    getMyWorkspaceCompletion(workspaceId)
      .then((summary) => {
        if (!cancelled) setState({ status: "ready", summary });
      })
      .catch((err: unknown) => {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load completion status.",
        });
      });
    return () => {
      cancelled = true;
    };
  }, [workspaceId]);

  if (state.status === "loading") {
    return (
      <section aria-busy="true" aria-label="Loading completion status">
        <div className="h-20 animate-pulse rounded-lg bg-muted" />
      </section>
    );
  }

  if (state.status === "error") {
    return <p className="text-sm text-destructive">{state.message}</p>;
  }

  const { summary } = state;

  return (
    <section className="flex flex-col gap-3">
      <h2 className="text-sm font-semibold tracking-wider text-muted-foreground uppercase">
        Completion
      </h2>
      <Card>
        <CardContent className="flex flex-col gap-3 py-4">
          <div className="flex flex-wrap items-center gap-2">
            <p className="font-medium">
              Requirements: {summary.completed_count} / {summary.required_count} complete
            </p>
            {summary.requirements_met && (
              <Badge className="bg-emerald-600 text-white hover:bg-emerald-600">Met</Badge>
            )}
          </div>

          {summary.outstanding.length > 0 && (
            <div>
              <p className="text-xs font-semibold tracking-wider text-muted-foreground uppercase">
                Outstanding
              </p>
              <ul className="mt-1 flex flex-col gap-1">
                {summary.outstanding.map((o) => (
                  <li key={o.id} className="flex items-center gap-1.5 text-sm">
                    <Circle className="size-3 shrink-0 text-muted-foreground" />
                    {o.title}
                  </li>
                ))}
              </ul>
            </div>
          )}

          <div className="flex items-center gap-1.5 text-sm">
            <span className="text-muted-foreground">Industry verification:</span>
            {summary.industry_verified ? (
              <span className="flex items-center gap-1 font-medium text-emerald-700 dark:text-emerald-400">
                <CheckCircle2 className="size-4" /> Completed
              </span>
            ) : (
              <span className="text-muted-foreground">Pending</span>
            )}
          </div>

          {!summary.industry_verified && (
            <p className="text-sm text-muted-foreground">
              {summary.requirements_met
                ? "Internship completion pending industry verification."
                : "Complete the remaining requirements."}
            </p>
          )}

          {summary.certificate && (
            <div className="flex flex-col gap-2 rounded-lg border border-emerald-600/30 bg-emerald-600/5 p-3">
              <div className="flex items-center gap-2">
                <Award className="size-5 text-emerald-600" />
                <p className="font-medium">Internship completed</p>
              </div>
              <dl className="grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-sm">
                <dt className="text-muted-foreground">Certificate number</dt>
                <dd className="font-mono">{summary.certificate.certificate_number}</dd>
                <dt className="text-muted-foreground">Issued</dt>
                <dd>{fmt(summary.certificate.issued_at)}</dd>
                <dt className="text-muted-foreground">Company</dt>
                <dd>{summary.certificate.company_name ?? "—"}</dd>
                <dt className="text-muted-foreground">Internship</dt>
                <dd>{summary.certificate.internship_title ?? "—"}</dd>
              </dl>
              {summary.certificate.skills.length > 0 && (
                <div className="flex flex-wrap gap-1.5">
                  {summary.certificate.skills.map((s) => (
                    <Badge key={s.skill_id} variant="secondary">
                      {s.skill_name}
                    </Badge>
                  ))}
                </div>
              )}
              <Link
                href={`/certificates/verify/${encodeURIComponent(summary.certificate.certificate_number)}`}
                target="_blank"
                rel="noopener noreferrer"
                className="inline-flex w-fit items-center gap-1 text-sm text-primary hover:underline"
              >
                Verify this certificate <ExternalLink className="size-3.5" />
              </Link>
            </div>
          )}
        </CardContent>
      </Card>
    </section>
  );
}
