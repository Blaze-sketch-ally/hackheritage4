"use client";

import { useEffect, useState } from "react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { getInstitutionDepartments } from "@/lib/institution/departments";
import { searchIndustryPartnerCompanies } from "@/lib/institution/industry-partners";
import type { DepartmentSummary } from "@/types/institution-department";
import type { CompanyOption } from "@/types/institution-industry";
import type { ReportType } from "@/types/institution-reports";
import { EVENT_TYPE_LABELS, EVENT_TYPES } from "@/types/institution-event";
import { COLLABORATION_STATUS_LABELS, COLLABORATION_STATUSES } from "@/types/industry-collaboration";

const ALL = "__all__";

export interface ReportFilterState {
  departmentId: string | null;
  batch: number | null;
  companyId: string | null;
  status: string | null;
  eventType: string | null;
  collaborationStatus: string | null;
  dateFrom: string | null;
  dateTo: string | null;
}

export const EMPTY_FILTERS: ReportFilterState = {
  departmentId: null,
  batch: null,
  companyId: null,
  status: null,
  eventType: null,
  collaborationStatus: null,
  dateFrom: null,
  dateTo: null,
};

const PLACEMENT_STATUS_OPTIONS = ["PLACED", "APPLYING", "NOT_PARTICIPATING"];
const EVENT_STATUS_OPTIONS = ["DRAFT", "PUBLISHED", "ONGOING", "COMPLETED", "CANCELLED"];

/**
 * Only the filters the selected report's backend can actually apply are
 * shown (Step 5) -- e.g. the Internship Report is institution-wide only
 * (see its own `note`), so no department/batch controls render for it.
 */
export function ReportFilters({
  reportType,
  value,
  onChange,
}: {
  reportType: ReportType;
  value: ReportFilterState;
  onChange: (next: ReportFilterState) => void;
}) {
  const [departments, setDepartments] = useState<DepartmentSummary[]>([]);
  const [companySearch, setCompanySearch] = useState("");
  const [companyOptions, setCompanyOptions] = useState<CompanyOption[]>([]);

  useEffect(() => {
    if (reportType !== "PLACEMENT" && reportType !== "STUDENT") return;
    getInstitutionDepartments()
      .then(({ departments: rows }) => setDepartments(rows))
      .catch(() => setDepartments([]));
  }, [reportType]);

  useEffect(() => {
    if (reportType !== "INDUSTRY") return;
    let cancelled = false;
    const timer = setTimeout(() => {
      searchIndustryPartnerCompanies(companySearch)
        .then(({ companies }) => {
          if (!cancelled) setCompanyOptions(companies);
        })
        .catch(() => {
          if (!cancelled) setCompanyOptions([]);
        });
    }, 250);
    return () => {
      cancelled = true;
      clearTimeout(timer);
    };
  }, [reportType, companySearch]);

  function set<K extends keyof ReportFilterState>(key: K, val: ReportFilterState[K]) {
    onChange({ ...value, [key]: val });
  }

  const showDepartmentBatch = reportType === "PLACEMENT" || reportType === "STUDENT";
  const showDateRange = reportType === "PLACEMENT";
  const showPlacementStatus = reportType === "STUDENT";
  const showCompany = reportType === "INDUSTRY";
  const showEventFilters = reportType === "EVENTS";
  const showCollaborationStatus = reportType === "COLLABORATION";

  const nothingToShow =
    !showDepartmentBatch && !showDateRange && !showPlacementStatus && !showCompany && !showEventFilters && !showCollaborationStatus;

  if (nothingToShow) {
    return <p className="text-sm text-muted-foreground">This report is always institution-wide -- no filters apply.</p>;
  }

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      {showDepartmentBatch ? (
        <div className="space-y-1.5">
          <Label>Department</Label>
          <Select value={value.departmentId ?? ALL} onValueChange={(v) => set("departmentId", v === ALL ? null : v)}>
            <SelectTrigger className="w-full" aria-label="Filter by department">
              <SelectValue placeholder="All departments" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All departments</SelectItem>
              {departments.map((d) => (
                <SelectItem key={d.id} value={d.id}>
                  {d.name}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {showDepartmentBatch ? (
        <div className="space-y-1.5">
          <Label>Batch</Label>
          <Input
            type="number"
            placeholder="e.g. 2026"
            value={value.batch ?? ""}
            onChange={(e) => set("batch", e.target.value ? Number(e.target.value) : null)}
            aria-label="Filter by batch"
          />
        </div>
      ) : null}

      {showPlacementStatus ? (
        <div className="space-y-1.5">
          <Label>Placement Status</Label>
          <Select value={value.status ?? ALL} onValueChange={(v) => set("status", v === ALL ? null : v)}>
            <SelectTrigger className="w-full" aria-label="Filter by placement status">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {PLACEMENT_STATUS_OPTIONS.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {showDateRange ? (
        <>
          <div className="space-y-1.5">
            <Label>Date From</Label>
            <Input
              type="date"
              value={value.dateFrom ?? ""}
              onChange={(e) => set("dateFrom", e.target.value || null)}
              aria-label="Date from"
            />
          </div>
          <div className="space-y-1.5">
            <Label>Date To</Label>
            <Input
              type="date"
              value={value.dateTo ?? ""}
              onChange={(e) => set("dateTo", e.target.value || null)}
              aria-label="Date to"
            />
          </div>
        </>
      ) : null}

      {showCompany ? (
        <div className="space-y-1.5 sm:col-span-2">
          <Label>Company</Label>
          <Input
            value={companySearch}
            onChange={(e) => setCompanySearch(e.target.value)}
            placeholder="Search companies..."
            aria-label="Search companies"
          />
          <Select value={value.companyId ?? ALL} onValueChange={(v) => set("companyId", v === ALL ? null : v)}>
            <SelectTrigger className="w-full" aria-label="Filter by company">
              <SelectValue placeholder="All companies" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All companies</SelectItem>
              {companyOptions.map((c) => (
                <SelectItem key={c.id} value={c.id}>
                  {c.company_name ?? "(unnamed company)"}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}

      {showEventFilters ? (
        <>
          <div className="space-y-1.5">
            <Label>Event Type</Label>
            <Select value={value.eventType ?? ALL} onValueChange={(v) => set("eventType", v === ALL ? null : v)}>
              <SelectTrigger className="w-full" aria-label="Filter by event type">
                <SelectValue placeholder="All types" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All types</SelectItem>
                {EVENT_TYPES.map((t) => (
                  <SelectItem key={t} value={t}>
                    {EVENT_TYPE_LABELS[t]}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
          <div className="space-y-1.5">
            <Label>Event Status</Label>
            <Select value={value.status ?? ALL} onValueChange={(v) => set("status", v === ALL ? null : v)}>
              <SelectTrigger className="w-full" aria-label="Filter by event status">
                <SelectValue placeholder="All statuses" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value={ALL}>All statuses</SelectItem>
                {EVENT_STATUS_OPTIONS.map((s) => (
                  <SelectItem key={s} value={s}>
                    {s}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>
        </>
      ) : null}

      {showCollaborationStatus ? (
        <div className="space-y-1.5">
          <Label>Collaboration Status</Label>
          <Select
            value={value.collaborationStatus ?? ALL}
            onValueChange={(v) => set("collaborationStatus", v === ALL ? null : v)}
          >
            <SelectTrigger className="w-full" aria-label="Filter by collaboration status">
              <SelectValue placeholder="All statuses" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value={ALL}>All statuses</SelectItem>
              {COLLABORATION_STATUSES.filter((s) => s !== "DRAFT").map((s) => (
                <SelectItem key={s} value={s}>
                  {COLLABORATION_STATUS_LABELS[s]}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      ) : null}
    </div>
  );
}
