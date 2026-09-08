"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { Briefcase, Info, UserCheck } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Loading } from "@/components/common/loading";
import { ErrorState } from "@/components/common/error-state";
import { ApiError } from "@/lib/api";
import {
  getAvailableInternships,
  getInstitutionInternshipOverview,
  getInstitutionInternships,
  removeInstitutionInternship,
  selectInstitutionInternship,
} from "@/lib/institution/internships";
import type {
  AvailableInternshipListResponse,
  InstitutionInternshipListResponse,
  InstitutionInternshipOverviewResponse,
} from "@/types/institution-internship";
import { InternshipKpis } from "@/components/institution/internships/internship-kpis";
import { InternshipsTable } from "@/components/institution/internships/internships-table";
import { AvailableInternshipsTable } from "@/components/institution/internships/available-internships-table";
import { InternshipDepartmentBreakdown } from "@/components/institution/internships/internship-department-breakdown";
import { InternshipCompanyBreakdown } from "@/components/institution/internships/internship-company-breakdown";
import { InternshipModeStipend } from "@/components/institution/internships/internship-mode-stipend";

type CuratedState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | {
      status: "ready";
      list: InstitutionInternshipListResponse;
      overview: InstitutionInternshipOverviewResponse;
    };

type AvailableState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; list: AvailableInternshipListResponse };

/**
 * Institution-Curated Internships: the default tab shows only internships
 * this institution has explicitly selected -- never every internship on
 * the platform. "Browse Available Internships" is where new ones are
 * discovered and added.
 */
export function InstitutionInternshipsView() {
  const [tab, setTab] = useState<"curated" | "available">("curated");
  const [curated, setCurated] = useState<CuratedState>({ status: "loading" });
  const [curatedReloadKey, setCuratedReloadKey] = useState(0);
  const [available, setAvailable] = useState<AvailableState>({ status: "idle" });
  const [pendingId, setPendingId] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([getInstitutionInternships(), getInstitutionInternshipOverview()])
      .then(([list, overview]) => {
        if (!cancelled) setCurated({ status: "ready", list, overview });
      })
      .catch((err) => {
        if (cancelled) return;
        setCurated({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load internships."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [curatedReloadKey]);

  function reloadCurated() {
    setCurated({ status: "loading" });
    setCuratedReloadKey((k) => k + 1);
  }

  function loadAvailable() {
    setAvailable({ status: "loading" });
    getAvailableInternships()
      .then((list) => setAvailable({ status: "ready", list }))
      .catch((err) => {
        setAvailable({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load available internships."),
        });
      });
  }

  function handleTabChange(value: unknown) {
    const next = value === "available" ? "available" : "curated";
    setTab(next);
    if (next === "available" && available.status === "idle") {
      loadAvailable();
    }
  }

  async function handleAdd(internshipId: string) {
    setPendingId(internshipId);
    try {
      await selectInstitutionInternship(internshipId);
      setAvailable((prev) =>
        prev.status === "ready"
          ? { status: "ready", list: { ...prev.list, internships: prev.list.internships.filter((r) => r.id !== internshipId) } }
          : prev,
      );
      reloadCurated();
    } catch {
      // Surfaced implicitly: the row stays in Available and can be retried.
    } finally {
      setPendingId(null);
    }
  }

  async function handleRemove(internshipId: string) {
    setPendingId(internshipId);
    try {
      await removeInstitutionInternship(internshipId);
      reloadCurated();
      setAvailable({ status: "idle" });
    } catch {
      // Surfaced implicitly: the row stays in the curated list and can be retried.
    } finally {
      setPendingId(null);
    }
  }

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-col gap-2 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Internships</h1>
          <p className="text-sm text-muted-foreground">
            Internships your institution has explicitly selected and curated -- their applications, selections and
            estimated participation.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          render={<Link href="/institution/students?internship_status=SELECTED" />}
        >
          <UserCheck className="size-4" /> View selected students
        </Button>
      </div>

      <Tabs value={tab} onValueChange={handleTabChange}>
        <TabsList>
          <TabsTrigger value="curated">Selected / Curated</TabsTrigger>
          <TabsTrigger value="available">Browse Available Internships</TabsTrigger>
        </TabsList>

        <TabsContent value="curated" className="pt-4">
          {curated.status === "loading" ? <Loading label="Loading internships…" className="py-16" /> : null}
          {curated.status === "error" ? (
            <ErrorState
              message={
                curated.error.status === 401 ? "Your session has expired. Please sign in again." : curated.error.message
              }
              onRetry={curated.error.status !== 401 ? reloadCurated : undefined}
            />
          ) : null}
          {curated.status === "ready" ? (
            <CuratedReady
              list={curated.list}
              overview={curated.overview}
              onRemove={handleRemove}
              removingId={pendingId}
            />
          ) : null}
        </TabsContent>

        <TabsContent value="available" className="pt-4">
          {available.status === "idle" || available.status === "loading" ? (
            <Loading label="Loading available internships…" className="py-16" />
          ) : null}
          {available.status === "error" ? (
            <ErrorState message={available.error.message} onRetry={loadAvailable} />
          ) : null}
          {available.status === "ready" ? (
            <AvailableInternshipsTable
              internships={available.list.internships}
              modeOptions={available.list.mode_options}
              onAdd={handleAdd}
              addingId={pendingId}
            />
          ) : null}
        </TabsContent>
      </Tabs>
    </div>
  );
}

function CuratedReady({
  list,
  overview,
  onRemove,
  removingId,
}: {
  list: InstitutionInternshipListResponse;
  overview: InstitutionInternshipOverviewResponse;
  onRemove: (internshipId: string) => void;
  removingId: string | null;
}) {
  return (
    <div className="space-y-6">
      <InternshipKpis kpis={overview.kpis} />

      <InternshipsTable
        internships={list.internships}
        statusOptions={list.status_options}
        modeOptions={list.mode_options}
        onRemove={onRemove}
        removingId={removingId}
      />

      <div className="grid gap-6 lg:grid-cols-2">
        <InternshipDepartmentBreakdown departments={overview.departments} />
        <InternshipCompanyBreakdown companies={overview.companies} />
      </div>

      <InternshipModeStipend modes={overview.mode_distribution} stipend={overview.stipend} />

      {overview.kpis.curated_internships === 0 && list.internships.length === 0 ? null : (
        <div className="flex items-center gap-2 text-xs text-muted-foreground">
          <Briefcase className="size-3.5" aria-hidden="true" />
          {overview.kpis.applicants} of your students have applied to your curated internships so far.
        </div>
      )}

      <div className="space-y-2">
        {[overview.curation_note, overview.tenancy_note, overview.eligibility_note, overview.participation_note].map(
          (note) => (
            <p
              key={note}
              className="flex items-start gap-1.5 rounded-lg border border-dashed px-3 py-2 text-xs text-muted-foreground"
            >
              <Info className="mt-0.5 size-3.5 shrink-0" aria-hidden="true" />
              {note}
            </p>
          ),
        )}
      </div>
    </div>
  );
}
