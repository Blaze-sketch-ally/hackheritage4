"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Building2, CalendarClock, CheckCircle2, Loader2, MapPin, RefreshCw, Users } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import {
  Dialog,
  DialogClose,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { expressInterest, listFacultyOpportunities } from "@/lib/faculty/opportunities";
import {
  OPPORTUNITY_SOURCES,
  OPPORTUNITY_SOURCE_LABELS,
  type FacultyOpportunity,
  type OpportunitySource,
} from "@/types/faculty-opportunity";

/** Real data only -- sourced from industry_faculty_opportunities /
 * institution_faculty_opportunities (Phase F3.4), NOT the Student-facing
 * industry_projects/training/workshops/mentorship tables F3.2 originally
 * (incorrectly) used. Faculty may now express genuine interest here --
 * that action creates a real DRAFT->SUBMITTED expression of interest,
 * not a decorative button. */

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; opportunities: FacultyOpportunity[] };

export function FacultyOpportunitiesView() {
  const [source, setSource] = useState<OpportunitySource | null>(null);
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [activeOpportunity, setActiveOpportunity] = useState<FacultyOpportunity | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!cancelled) setState({ status: "loading" });
      try {
        const { opportunities } = await listFacultyOpportunities(source ?? undefined);
        if (cancelled) return;
        setState({ status: "ready", opportunities });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load opportunities.",
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [source, reloadKey]);

  return (
    <div className="flex flex-col gap-4">
      <div className="flex flex-wrap gap-1.5">
        <Button size="sm" variant={source === null ? "default" : "outline"} onClick={() => setSource(null)}>
          All
        </Button>
        {OPPORTUNITY_SOURCES.map((s) => (
          <Button key={s} size="sm" variant={source === s ? "default" : "outline"} onClick={() => setSource(s)}>
            {OPPORTUNITY_SOURCE_LABELS[s]}
          </Button>
        ))}
      </div>

      {state.status === "loading" && (
        <Card>
          <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
            <Loader2 className="size-5 animate-spin" /> Loading opportunities…
          </CardContent>
        </Card>
      )}

      {state.status === "error" && (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <AlertCircle className="size-8 text-destructive" />
            <p className="font-medium">{state.message}</p>
            <Button size="sm" onClick={() => setReloadKey((k) => k + 1)}>
              <RefreshCw className="size-3.5" /> Try again
            </Button>
          </CardContent>
        </Card>
      )}

      {state.status === "ready" && state.opportunities.length === 0 && (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No published opportunities right now
            {source ? ` from ${OPPORTUNITY_SOURCE_LABELS[source]}` : ""}. Check back later.
          </CardContent>
        </Card>
      )}

      {state.status === "ready" && state.opportunities.length > 0 && (
        <div className="grid gap-4 sm:grid-cols-2">
          {state.opportunities.map((o) => (
            <OpportunityCard key={`${o.source}-${o.id}`} opportunity={o} onExpressInterest={() => setActiveOpportunity(o)} />
          ))}
        </div>
      )}

      <ExpressInterestDialog
        key={activeOpportunity ? `${activeOpportunity.source}-${activeOpportunity.id}` : "closed"}
        opportunity={activeOpportunity}
        onClose={() => setActiveOpportunity(null)}
      />
    </div>
  );
}

function OpportunityCard({
  opportunity,
  onExpressInterest,
}: {
  opportunity: FacultyOpportunity;
  onExpressInterest: () => void;
}) {
  return (
    <Card>
      <CardContent className="flex flex-col gap-2 py-4">
        <div className="flex items-start justify-between gap-2">
          <p className="font-medium">{opportunity.title}</p>
          <Badge variant="outline" className="shrink-0">
            {OPPORTUNITY_SOURCE_LABELS[opportunity.source]}
          </Badge>
        </div>
        {opportunity.owner_name && (
          <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
            <Building2 className="size-3.5 shrink-0" /> {opportunity.owner_name}
          </p>
        )}
        {opportunity.description && (
          <p className="line-clamp-2 text-sm text-muted-foreground">{opportunity.description}</p>
        )}
        <div className="flex flex-wrap gap-3 text-xs text-muted-foreground">
          {opportunity.location && (
            <span className="flex items-center gap-1">
              <MapPin className="size-3" /> {opportunity.location}
            </span>
          )}
          {opportunity.capacity !== null && (
            <span className="flex items-center gap-1">
              <Users className="size-3" /> {opportunity.capacity} seats
            </span>
          )}
          {opportunity.application_deadline && (
            <span className="flex items-center gap-1">
              <CalendarClock className="size-3" /> Deadline {opportunity.application_deadline}
            </span>
          )}
        </div>
        <div>
          <Button size="sm" onClick={onExpressInterest}>
            Express Interest
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

function ExpressInterestDialog({
  opportunity,
  onClose,
}: {
  opportunity: FacultyOpportunity | null;
  onClose: () => void;
}) {
  // A fresh `key` from the parent (per opportunity) remounts this
  // component whenever a different opportunity is targeted, so these
  // reset naturally -- no effect-driven reset needed.
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  async function handleSubmit() {
    if (!opportunity) return;
    setSubmitting(true);
    setError(null);
    try {
      await expressInterest(opportunity.source, opportunity.id, message);
      setSubmitted(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Could not submit your expression of interest.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <Dialog open={opportunity !== null} onOpenChange={(open) => !open && onClose()}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Express interest</DialogTitle>
          <DialogDescription>{opportunity?.title}</DialogDescription>
        </DialogHeader>

        {submitted ? (
          <p className="flex items-center gap-1.5 text-sm text-emerald-600 dark:text-emerald-400">
            <CheckCircle2 className="size-3.5 shrink-0" /> Your expression of interest has been submitted.
          </p>
        ) : (
          <div className="flex flex-col gap-2">
            <Textarea
              placeholder="Optional message to the opportunity owner…"
              rows={4}
              value={message}
              onChange={(e) => setMessage(e.target.value)}
            />
            {error && (
              <p className="flex items-center gap-1.5 text-sm text-destructive">
                <AlertCircle className="size-3.5 shrink-0" /> {error}
              </p>
            )}
          </div>
        )}

        <DialogFooter>
          <DialogClose render={<Button variant="outline" />}>{submitted ? "Close" : "Cancel"}</DialogClose>
          {!submitted && (
            <Button onClick={() => void handleSubmit()} disabled={submitting}>
              {submitting ? <Loader2 className="size-3.5 animate-spin" /> : null}
              Submit
            </Button>
          )}
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
