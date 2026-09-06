"use client";

import { useEffect, useMemo, useState } from "react";
import { AlertCircle, Inbox, RefreshCw, Search } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { ConfirmationDialog } from "@/components/common/confirmation-dialog";
import { EmptyState } from "@/components/common/empty-state";
import { FormError } from "@/components/auth/form-error";
import { FormSuccess } from "@/components/auth/form-success";
import { Filters } from "@/components/common/filters";
import { SearchBar } from "@/components/common/search-bar";
import { ApiError } from "@/lib/api";
import {
  getApplications,
  getApplicationsSummary,
  updateApplicationStatus,
} from "@/lib/industry/applications";
import {
  APPLICATION_STATUSES,
  APPLICATION_STATUS_LABELS,
  OPPORTUNITY_TYPES,
  OPPORTUNITY_TYPE_LABELS,
  TRANSITION_LABELS,
  applicantDisplayName,
  type Application,
  type ApplicationStatus,
  type ApplicationSummary,
  type IndustrySettableStatus,
} from "@/types/application";
import { ApplicantTable } from "@/components/industry/applicant-table";
import { CandidateCard } from "@/components/industry/candidate-card";
import { RecruitmentFunnel } from "@/components/industry/recruitment-funnel";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; applications: Application[]; summary: ApplicationSummary | null };

const EMPTY_SUMMARY: ApplicationSummary = {
  counts: {
    APPLIED: 0,
    UNDER_REVIEW: 0,
    SHORTLISTED: 0,
    INTERVIEW_SCHEDULED: 0,
    SELECTED: 0,
    REJECTED: 0,
    WITHDRAWN: 0,
  },
  total: 0,
};

/** The one recruitment surface behind every /industry recruitment page:
 * the full Applicants view (table + funnel + filters) and the
 * stage-locked views (Shortlisted / Interviews / Selected — a filtered
 * list of cards). All consume the same Phase 7 application API. */
export function RecruitmentApplications({
  heading,
  description,
  emptyTitle,
  emptyDescription,
  /** When set, only applications in these statuses are shown (stage views). */
  lockedStatuses,
  showFunnel = false,
  showStatusFilter = false,
  showTypeFilter = false,
  layout = "cards",
}: {
  heading: string;
  description: string;
  emptyTitle: string;
  emptyDescription?: string;
  lockedStatuses?: ApplicationStatus[];
  showFunnel?: boolean;
  showStatusFilter?: boolean;
  showTypeFilter?: boolean;
  layout?: "table" | "cards";
}) {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [search, setSearch] = useState("");
  const [statusFilter, setStatusFilter] = useState<ApplicationStatus | "all">("all");
  const [typeFilter, setTypeFilter] = useState("all");

  const [pendingId, setPendingId] = useState<string | null>(null);
  const [confirming, setConfirming] = useState<{ id: string; target: IndustrySettableStatus } | null>(
    null,
  );
  const [actionError, setActionError] = useState<string | null>(null);
  const [actionSuccess, setActionSuccess] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    Promise.all([
      getApplications(),
      showFunnel ? getApplicationsSummary() : Promise.resolve(null),
    ])
      .then(([{ applications }, summary]) => {
        if (!cancelled) setState({ status: "ready", applications, summary });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load applications."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey, showFunnel]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  const inScope = useMemo(() => {
    if (state.status !== "ready") return [];
    return lockedStatuses
      ? state.applications.filter((a) => lockedStatuses.includes(a.status))
      : state.applications;
  }, [state, lockedStatuses]);

  const visible = useMemo(() => {
    const query = search.trim().toLowerCase();
    return inScope.filter((app) => {
      const matchesStatus = statusFilter === "all" || app.status === statusFilter;
      const matchesType = typeFilter === "all" || app.opportunity_type === typeFilter;
      const haystack =
        `${app.opportunity?.title ?? ""} ${applicantDisplayName(app)}`.toLowerCase();
      const matchesSearch = !query || haystack.includes(query);
      return matchesStatus && matchesType && matchesSearch;
    });
  }, [inScope, search, statusFilter, typeFilter]);

  async function runTransition(id: string, target: IndustrySettableStatus) {
    setConfirming(null);
    setPendingId(id);
    setActionError(null);
    setActionSuccess(null);
    try {
      const updated = await updateApplicationStatus(id, target);
      setState((prev) => {
        if (prev.status !== "ready") return prev;
        const before = prev.applications.find((a) => a.id === id);
        let summary = prev.summary;
        if (summary && before && before.status !== updated.status) {
          const counts = { ...summary.counts };
          counts[before.status] = Math.max(0, (counts[before.status] ?? 0) - 1);
          counts[updated.status] = (counts[updated.status] ?? 0) + 1;
          summary = { ...summary, counts };
        }
        return {
          ...prev,
          applications: prev.applications.map((a) => (a.id === id ? updated : a)),
          summary,
        };
      });
      setActionSuccess(`Moved to “${APPLICATION_STATUS_LABELS[target]}”.`);
    } catch (err) {
      setActionError(
        err instanceof ApiError ? err.message : "Something went wrong. Please try again.",
      );
    } finally {
      setPendingId(null);
    }
  }

  const statusOptions = [
    { value: "all", label: "All statuses" },
    ...APPLICATION_STATUSES.map((s) => ({ value: s, label: APPLICATION_STATUS_LABELS[s] })),
  ];
  const typeOptions = [
    { value: "all", label: "All types" },
    ...OPPORTUNITY_TYPES.map((t) => ({ value: t, label: OPPORTUNITY_TYPE_LABELS[t] })),
  ];

  const showToolbar = showStatusFilter || showTypeFilter || inScope.length > 0;

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">{heading}</h1>
        <p className="text-sm text-muted-foreground">{description}</p>
      </div>

      <FormError message={actionError} />
      <FormSuccess message={actionSuccess} />

      {state.status === "loading" ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground" aria-busy="true">
            Loading applications…
          </CardContent>
        </Card>
      ) : null}

      {state.status === "error" ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" aria-hidden="true" />
            <div>
              <p className="font-medium">
                {state.error.status === 401
                  ? "Your session has expired. Please sign in again."
                  : "Could not load applications."}
              </p>
              <p className="text-sm text-muted-foreground">{state.error.message}</p>
            </div>
            {state.error.status !== 401 ? (
              <Button variant="outline" size="sm" onClick={reload}>
                <RefreshCw className="size-3.5" /> Try again
              </Button>
            ) : null}
          </CardContent>
        </Card>
      ) : null}

      {state.status === "ready" ? (
        <>
          {showFunnel ? (
            <RecruitmentFunnel
              summary={state.summary ?? EMPTY_SUMMARY}
              activeStatus={statusFilter}
              onStageClick={(status) =>
                setStatusFilter((prev) => (prev === status ? "all" : status))
              }
            />
          ) : null}

          {inScope.length === 0 ? (
            <EmptyState icon={Inbox} title={emptyTitle} description={emptyDescription} />
          ) : (
            <>
              {showToolbar ? (
                <div className="flex flex-col gap-3 sm:flex-row">
                  <SearchBar
                    value={search}
                    onChange={setSearch}
                    placeholder="Search by opportunity or applicant..."
                    aria-label="Search applications"
                  />
                  {showStatusFilter ? (
                    <Filters
                      value={statusFilter}
                      onChange={(v) => setStatusFilter(v as ApplicationStatus | "all")}
                      options={statusOptions}
                      aria-label="Filter by status"
                    />
                  ) : null}
                  {showTypeFilter ? (
                    <Filters
                      value={typeFilter}
                      onChange={setTypeFilter}
                      options={typeOptions}
                      aria-label="Filter by opportunity type"
                    />
                  ) : null}
                </div>
              ) : null}

              {visible.length === 0 ? (
                <EmptyState icon={Search} title="No applications match your filters" />
              ) : layout === "table" ? (
                <ApplicantTable
                  applications={visible}
                  pendingId={pendingId}
                  onPick={(id, target) => setConfirming({ id, target })}
                />
              ) : (
                <div className="space-y-3">
                  {visible.map((application) => (
                    <CandidateCard
                      key={application.id}
                      application={application}
                      pending={pendingId === application.id}
                      onPick={(target) => setConfirming({ id: application.id, target })}
                    />
                  ))}
                </div>
              )}
            </>
          )}
        </>
      ) : null}

      <ConfirmationDialog
        open={!!confirming}
        onOpenChange={(open) => !open && setConfirming(null)}
        title={confirming ? `${TRANSITION_LABELS[confirming.target]} this application?` : ""}
        description={
          confirming?.target === "REJECTED"
            ? "The applicant will see their application marked as rejected."
            : "This updates where the application sits in your recruitment pipeline."
        }
        confirmLabel={confirming ? TRANSITION_LABELS[confirming.target] : "Confirm"}
        destructive={confirming?.target === "REJECTED"}
        loading={!!pendingId}
        onConfirm={() => confirming && runTransition(confirming.id, confirming.target)}
      />
    </div>
  );
}
