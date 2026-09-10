"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, Info, Pencil } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { ApiError } from "@/lib/api";
import { getIndustryPartner } from "@/lib/institution/industry-partners";
import type { IndustryPartnerDetail as IndustryPartnerDetailData } from "@/types/institution-industry";
import { RELATIONSHIP_STATUS_LABELS, RELATIONSHIP_TYPE_LABELS } from "@/types/institution-industry";
import { IndustryPartnerForm } from "@/components/institution/industry-partners/industry-partner-form";
import { CompanyConnectionsCard } from "@/components/institution/industry-partners/company-connections-card";
import { CompanyEventsCard } from "@/components/institution/industry-partners/company-events-card";
import { CompanyInternshipsCard } from "@/components/institution/industry-partners/company-internships-card";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; partner: IndustryPartnerDetailData };

const STATUS_VARIANT: Record<string, "default" | "secondary" | "outline"> = {
  ACTIVE: "default",
  PROSPECT: "secondary",
  INACTIVE: "outline",
};

function formatDate(value: string | null): string {
  if (!value) return "No recorded activity";
  return new Date(value).toLocaleDateString(undefined, { year: "numeric", month: "short", day: "numeric" });
}

/** Company Detail (Phase 8, Part 8-14): overview + institution-specific
 * recruitment history. Never exposes another institution's activity or
 * industry-private notes -- see `tenancy_note` / `privacy_note`, always
 * rendered. */
export function IndustryPartnerDetail({ industryId }: { industryId: string }) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [formOpen, setFormOpen] = useState(false);

  useEffect(() => {
    let cancelled = false;
    getIndustryPartner(industryId)
      .then((partner) => {
        if (!cancelled) setState({ status: "ready", partner });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load this industry partner."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [industryId, reloadKey]);

  function handleSaved() {
    setFormOpen(false);
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  return (
    <div className="mx-auto max-w-5xl space-y-6">
      <Button variant="ghost" size="sm" render={<Link href="/institution/industry-partners" />}>
        <ArrowLeft className="size-4" /> Back to Industry Partners
      </Button>

      {state.status === "loading" ? <Loading label="Loading industry partner…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={
            state.error.status === 404 ? "This company isn't visible to your institution." : state.error.message
          }
          onRetry={
            state.error.status !== 401 && state.error.status !== 404
              ? () => {
                  setState({ status: "loading" });
                  setReloadKey((k) => k + 1);
                }
              : undefined
          }
        />
      ) : null}

      {state.status === "ready" ? (
        <Ready partner={state.partner} onEdit={() => setFormOpen(true)} />
      ) : null}

      {state.status === "ready" ? (
        <IndustryPartnerForm
          open={formOpen}
          onOpenChange={setFormOpen}
          existing={{
            industryId,
            relationship: state.partner.has_explicit_relationship
              ? {
                  id: state.partner.relationship_id!,
                  industry_id: industryId,
                  relationship_type: state.partner.relationship_type!,
                  relationship_status: state.partner.relationship_status!,
                  notes: state.partner.notes,
                  created_at: null,
                  updated_at: null,
                }
              : null,
          }}
          existingCompanyName={state.partner.company_name}
          onSaved={handleSaved}
        />
      ) : null}
    </div>
  );
}

function Ready({ partner: p, onEdit }: { partner: IndustryPartnerDetailData; onEdit: () => void }) {
  return (
    <div className="space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">{p.company_name ?? "Unknown company"}</h1>
          <p className="text-sm text-muted-foreground">{p.industry_sector ?? "Sector not specified"}</p>
        </div>
        <Button variant="outline" size="sm" onClick={onEdit}>
          <Pencil className="size-4" /> {p.has_explicit_relationship ? "Edit Relationship" : "Track Relationship"}
        </Button>
      </div>

      <div className="grid gap-6 lg:grid-cols-2">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Company Overview</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            <p className="text-muted-foreground">{p.company_description ?? "No description provided."}</p>
            {[
              ["Company Size", p.company_size ?? "—"],
              ["Location", p.headquarters_location ?? "—"],
              ["Website", p.website_url ?? "—"],
            ].map(([label, value]) => (
              <div key={label as string} className="flex items-center justify-between">
                <span className="text-xs text-muted-foreground">{label}</span>
                <span className="font-medium">{value}</span>
              </div>
            ))}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Relationship</CardTitle>
          </CardHeader>
          <CardContent className="space-y-3 text-sm">
            {p.has_explicit_relationship ? (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Type</span>
                  <span className="font-medium">
                    {RELATIONSHIP_TYPE_LABELS[p.relationship_type ?? ""] ?? p.relationship_type}
                  </span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Status</span>
                  <Badge variant={STATUS_VARIANT[p.relationship_status ?? ""] ?? "outline"}>
                    {RELATIONSHIP_STATUS_LABELS[p.relationship_status ?? ""] ?? p.relationship_status}
                  </Badge>
                </div>
                {p.notes ? (
                  <div>
                    <span className="text-xs text-muted-foreground">Notes (private)</span>
                    <p className="mt-1">{p.notes}</p>
                  </div>
                ) : null}
              </>
            ) : (
              <p className="text-muted-foreground">
                No explicit relationship tracked yet -- this company appears here because of real activity below.
              </p>
            )}
            <div className="flex items-center justify-between border-t pt-3">
              <span className="text-xs text-muted-foreground">Last Activity</span>
              <span className="font-medium">{formatDate(p.last_activity_at)}</span>
            </div>
          </CardContent>
        </Card>
      </div>

      <div className="grid gap-6 lg:grid-cols-4">
        <Card>
          <CardHeader>
            <CardTitle className="text-base">Jobs</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Stat label="Opportunities" value={p.jobs.opportunities} />
            <Stat label="Applicants" value={p.jobs.applicants} />
            <Stat label="Selected Students" value={p.jobs.selected_students} />
            {p.jobs.titles.length > 0 ? (
              <p className="pt-1 text-xs text-muted-foreground">{p.jobs.titles.join(", ")}</p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Internships</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Stat label="Opportunities" value={p.internships.opportunities} />
            <Stat label="Applicants" value={p.internships.applicants} />
            <Stat label="Selected Offers" value={p.internships.selected} />
            <Stat label="Completed (estimated)" value={p.internships.completed} />
            {p.internships.titles.length > 0 ? (
              <p className="pt-1 text-xs text-muted-foreground">{p.internships.titles.join(", ")}</p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle className="text-base">Collaborations</CardTitle>
          </CardHeader>
          <CardContent className="space-y-2 text-sm">
            <Stat label="Count" value={p.collaborations.count} />
            {p.collaborations.count > 0 ? (
              <>
                <div className="flex items-center justify-between">
                  <span className="text-xs text-muted-foreground">Latest Status</span>
                  <span className="font-medium">{p.collaborations.latest_status}</span>
                </div>
                <p className="text-xs text-muted-foreground">{p.collaborations.latest_title}</p>
              </>
            ) : null}
            <Link
              href={
                p.company_name
                  ? `/institution/collaborations?company=${encodeURIComponent(p.company_name)}`
                  : "/institution/collaborations"
              }
              className="text-xs text-indigo-600 hover:underline dark:text-indigo-400"
            >
              View Collaborations →
            </Link>
          </CardContent>
        </Card>

        <CompanyConnectionsCard industryId={p.id} companyName={p.company_name} />
      </div>

      <Card>
        <CardHeader>
          <CardTitle className="text-base">Placement Drives</CardTitle>
          <p className="text-xs text-muted-foreground">
            {p.placement_drives.count} drive(s) · {p.placement_drives.unique_students_selected} unique student(s)
            selected via drives
          </p>
        </CardHeader>
        <CardContent>
          {p.placement_drives.drives.length === 0 ? (
            <p className="text-sm text-muted-foreground/70">No placement drives with this company yet.</p>
          ) : (
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>Drive</TableHead>
                  <TableHead>Status</TableHead>
                  <TableHead className="text-right">Applicants</TableHead>
                  <TableHead className="text-right">Selected</TableHead>
                  <TableHead className="text-right">Selection Rate</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {p.placement_drives.drives.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell className="font-medium">
                      <Link href={`/institution/placements/${d.id}`} className="hover:underline">
                        {d.title}
                      </Link>
                    </TableCell>
                    <TableCell>
                      <Badge variant="outline">{d.status}</Badge>
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{d.applied_count}</TableCell>
                    <TableCell className="text-right tabular-nums">{d.selected_count}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {d.selection_rate != null ? `${d.selection_rate}%` : "N/A"}
                    </TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          )}
        </CardContent>
      </Card>

      <CompanyInternshipsCard industryId={p.id} />

      <CompanyEventsCard industryId={p.id} />

      <div className="space-y-2">
        {[p.tenancy_note, p.privacy_note].map((note) => (
          <p
            key={note}
            className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground"
          >
            <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
            {note}
          </p>
        ))}
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="flex items-center justify-between">
      <span className="text-xs text-muted-foreground">{label}</span>
      <span className="font-medium tabular-nums">{value}</span>
    </div>
  );
}
