"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { getInstitutionInternships } from "@/lib/institution/internships";
import type { InstitutionInternshipRow } from "@/types/institution-internship";

/**
 * Company Detail's "Internships" section: internships from THIS company
 * that the institution has curated, fetched via
 * GET /institution/internships?company_id=... -- the same curated
 * directory the dedicated /institution/internships page uses. Links to
 * the full internship record; never duplicates internship content, and
 * never lets the institution edit the canonical posting.
 */
export function CompanyInternshipsCard({ industryId }: { industryId: string }) {
  const [internships, setInternships] = useState<InstitutionInternshipRow[] | null>(null);

  useEffect(() => {
    let cancelled = false;
    getInstitutionInternships({ company_id: industryId })
      .then(({ internships: rows }) => {
        if (!cancelled) setInternships(rows);
      })
      .catch(() => {
        if (!cancelled) setInternships([]);
      });
    return () => {
      cancelled = true;
    };
  }, [industryId]);

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Curated Internships</CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {internships == null ? (
          <p className="text-sm text-muted-foreground/70">Loading…</p>
        ) : internships.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <Briefcase className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">Your institution hasn&apos;t curated any internships from this company yet.</p>
          </div>
        ) : (
          <ul className="space-y-2">
            {internships.map((r) => (
              <li key={r.id} className="flex items-center justify-between gap-2 text-sm">
                <Link href={`/institution/internships/${r.id}`} className="min-w-0 truncate hover:underline">
                  {r.title}
                </Link>
                <Badge variant="outline">{r.status}</Badge>
              </li>
            ))}
          </ul>
        )}
        <Link
          href="/institution/internships"
          className="inline-block text-xs text-indigo-600 hover:underline dark:text-indigo-400"
        >
          Browse Available Internships →
        </Link>
      </CardContent>
    </Card>
  );
}
