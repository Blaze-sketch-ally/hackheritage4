"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Plus, Users } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { getIndustryConnections } from "@/lib/institution/industry-connections";
import type { IndustryConnectionRow } from "@/types/institution-industry-connection";
import { CONTACT_TYPE_LABELS } from "@/types/institution-industry-connection";
import { IndustryConnectionForm } from "@/components/institution/industry-connections/industry-connection-form";

/**
 * Company Detail's "Connections" section (Phase 9, Part 15/16) --
 * institution-scoped contacts for THIS company only, fetched via the
 * same GET /institution/industry-connections?industry_id=... endpoint
 * the dedicated /institution/industry-connections page uses. Shows a
 * short list, never duplicates the full connection records -- "View
 * All" links to the dedicated module.
 */
export function CompanyConnectionsCard({
  industryId,
  companyName,
}: {
  industryId: string;
  companyName: string | null;
}) {
  const [connections, setConnections] = useState<IndustryConnectionRow[] | null>(null);
  const [formOpen, setFormOpen] = useState(false);
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let cancelled = false;
    getIndustryConnections({ industry_id: industryId, is_active: true })
      .then(({ connections: rows }) => {
        if (!cancelled) setConnections(rows);
      })
      .catch(() => {
        if (!cancelled) setConnections([]);
      });
    return () => {
      cancelled = true;
    };
  }, [industryId, reloadKey]);

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2 space-y-0">
        <CardTitle className="text-base">Connections</CardTitle>
        <Button size="sm" variant="outline" onClick={() => setFormOpen(true)}>
          <Plus className="size-4" /> Add Contact
        </Button>
      </CardHeader>
      <CardContent className="space-y-3">
        {connections == null ? (
          <p className="text-sm text-muted-foreground/70">Loading…</p>
        ) : connections.length === 0 ? (
          <div className="flex flex-col items-center gap-2 py-4 text-center">
            <Users className="size-6 text-muted-foreground" aria-hidden="true" />
            <p className="text-sm text-muted-foreground">No contacts recorded for this company yet.</p>
          </div>
        ) : (
          <ul className="space-y-2">
            {connections.map((c) => (
              <li key={c.id} className="flex items-center justify-between gap-2 text-sm">
                <div className="min-w-0">
                  <p className="truncate font-medium">{c.contact_name}</p>
                  <p className="truncate text-xs text-muted-foreground">{c.designation ?? "—"}</p>
                </div>
                <Badge variant="outline">{CONTACT_TYPE_LABELS[c.contact_type] ?? c.contact_type}</Badge>
              </li>
            ))}
          </ul>
        )}
        <Link
          href="/institution/industry-connections"
          className="inline-block text-xs text-indigo-600 hover:underline dark:text-indigo-400"
        >
          View All Connections →
        </Link>
      </CardContent>

      <IndustryConnectionForm
        open={formOpen}
        onOpenChange={setFormOpen}
        presetCompanyId={industryId}
        presetCompanyName={companyName}
        onSaved={() => {
          setFormOpen(false);
          setReloadKey((k) => k + 1);
        }}
      />
    </Card>
  );
}
