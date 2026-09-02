"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Loader2, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { ApiError } from "@/lib/api";
import { useMentorCapability } from "@/lib/faculty/mentor-capability";
import {
  getMenteeProfile,
  getMentorshipNote,
  listMyMentorships,
  requestMentorship,
  saveMentorshipNote,
  updateMentorshipStatus,
} from "@/lib/faculty/mentorships";
import {
  MENTORSHIP_STATUS_LABELS,
  type FacultyStudentMentorship,
  type MenteeProfileBundle,
  type MentorshipStatus,
} from "@/types/faculty-mentorship";

/**
 * Phase F4.2 -- the dedicated Faculty Mentorship page. Deliberately its
 * own page (not folded into Opportunities/Applications/Engagements):
 * mentorship is an ongoing Faculty<->Student relationship with its own
 * lifecycle, distinct from Engagement's 1:1-per-EOI shape.
 *
 * No directory/browse UI here -- there is no "list students I could
 * mentor" endpoint (deliberately out of scope, see the F4.2 report's
 * Deferred section). Requesting a mentorship means typing in the other
 * party's account id directly.
 *
 * Every action here is re-authorized by the backend (require_faculty +
 * require_mentor_capability) and, independently, by RLS -- this
 * component's own capability check only improves the UX by disabling
 * actions the backend would reject anyway; it is never the security
 * boundary.
 */

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; mentorships: FacultyStudentMentorship[] };

type TransitionStatus = Extract<
  MentorshipStatus,
  "ACCEPTED" | "DECLINED" | "WITHDRAWN" | "ACTIVE" | "COMPLETED" | "ENDED"
>;

export function FacultyMentorshipView() {
  const capability = useMentorCapability();
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [targetId, setTargetId] = useState("");
  const [focusArea, setFocusArea] = useState("");
  const [requesting, setRequesting] = useState(false);
  const [requestError, setRequestError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const { mentorships } = await listMyMentorships();
        if (cancelled) return;
        setState({ status: "ready", mentorships });
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load your mentorships.",
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function refresh() {
    setReloadKey((k) => k + 1);
  }

  async function handleRequest() {
    setRequesting(true);
    setRequestError(null);
    try {
      await requestMentorship(targetId.trim(), focusArea.trim() || null);
      setTargetId("");
      setFocusArea("");
      refresh();
    } catch (err) {
      setRequestError(err instanceof ApiError ? err.message : "Could not create this mentorship request.");
    } finally {
      setRequesting(false);
    }
  }

  async function handleTransition(mentorshipId: string, status: TransitionStatus) {
    setBusyId(mentorshipId);
    setActionError(null);
    try {
      await updateMentorshipStatus(mentorshipId, status);
      refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not update this mentorship.");
    } finally {
      setBusyId(null);
    }
  }

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading your mentorships…
        </CardContent>
      </Card>
    );
  }

  if (state.status === "error") {
    return (
      <Card>
        <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
          <AlertCircle className="size-8 text-destructive" />
          <p className="font-medium">{state.message}</p>
          <Button size="sm" onClick={refresh}>
            <RefreshCw className="size-3.5" /> Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { mentorships } = state;
  const requests = mentorships.filter((m) => m.status === "REQUESTED" || m.status === "ACCEPTED");
  const active = mentorships.filter((m) => m.status === "ACTIVE");
  const history = mentorships.filter((m) => ["DECLINED", "WITHDRAWN", "COMPLETED", "ENDED"].includes(m.status));

  const canMentor = capability.status === "ready" && capability.canMentor;

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Request a mentorship</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          {capability.status === "ready" && !capability.canMentor && (
            <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
              <AlertCircle className="size-3.5 shrink-0" /> An Admin must grant you the mentor capability before you
              can request or accept mentorships.
            </p>
          )}
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="mentorship-student-id">Student ID</Label>
              <Input
                id="mentorship-student-id"
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                placeholder="The student's account id"
              />
            </div>
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="mentorship-focus-area">Focus area (optional)</Label>
              <Input id="mentorship-focus-area" value={focusArea} onChange={(e) => setFocusArea(e.target.value)} />
            </div>
          </div>
          {requestError && (
            <p className="flex items-center gap-1.5 text-sm text-destructive">
              <AlertCircle className="size-3.5 shrink-0" /> {requestError}
            </p>
          )}
          <div>
            <Button size="sm" disabled={requesting || !targetId.trim() || !canMentor} onClick={() => void handleRequest()}>
              Request mentorship
            </Button>
          </div>
        </CardContent>
      </Card>

      {actionError && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="size-3.5 shrink-0" /> {actionError}
        </p>
      )}

      <MentorshipSection
        title="Requests"
        emptyLabel="No pending mentorship requests."
        mentorships={requests}
        busyId={busyId}
        expandedId={expandedId}
        onExpand={setExpandedId}
        onTransition={handleTransition}
      />
      <MentorshipSection
        title="Active mentorships"
        emptyLabel="No active mentorships."
        mentorships={active}
        busyId={busyId}
        expandedId={expandedId}
        onExpand={setExpandedId}
        onTransition={handleTransition}
      />
      <MentorshipSection
        title="History"
        emptyLabel="No past mentorships."
        mentorships={history}
        busyId={busyId}
        expandedId={expandedId}
        onExpand={setExpandedId}
        onTransition={handleTransition}
      />
    </div>
  );
}

function MentorshipSection({
  title,
  emptyLabel,
  mentorships,
  busyId,
  expandedId,
  onExpand,
  onTransition,
}: {
  title: string;
  emptyLabel: string;
  mentorships: FacultyStudentMentorship[];
  busyId: string | null;
  expandedId: string | null;
  onExpand: (id: string | null) => void;
  onTransition: (mentorshipId: string, status: TransitionStatus) => void;
}) {
  return (
    <div>
      <h2 className="mb-2 text-sm font-semibold">{title}</h2>
      {mentorships.length === 0 ? (
        <Card>
          <CardContent className="py-6 text-center text-sm text-muted-foreground">{emptyLabel}</CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {mentorships.map((m) => {
            const busy = busyId === m.id;
            const iRequested = m.requested_by === m.faculty_id;
            return (
              <Card key={m.id}>
                <CardContent className="flex flex-col gap-3 py-4">
                  <div className="flex flex-col gap-2 sm:flex-row sm:items-center sm:justify-between">
                    <div className="min-w-0">
                      <p className="font-medium">Student #{m.student_id.slice(0, 8)}</p>
                      {m.focus_area && <p className="text-sm text-muted-foreground">{m.focus_area}</p>}
                    </div>
                    <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                      <Badge variant="outline">{MENTORSHIP_STATUS_LABELS[m.status]}</Badge>
                      {m.status === "REQUESTED" && iRequested && (
                        <Button size="sm" variant="outline" disabled={busy} onClick={() => onTransition(m.id, "WITHDRAWN")}>
                          Withdraw
                        </Button>
                      )}
                      {m.status === "REQUESTED" && !iRequested && (
                        <>
                          <Button size="sm" disabled={busy} onClick={() => onTransition(m.id, "ACCEPTED")}>
                            Accept
                          </Button>
                          <Button size="sm" variant="outline" disabled={busy} onClick={() => onTransition(m.id, "DECLINED")}>
                            Decline
                          </Button>
                        </>
                      )}
                      {m.status === "ACCEPTED" && (
                        <Button size="sm" disabled={busy} onClick={() => onTransition(m.id, "ACTIVE")}>
                          Activate
                        </Button>
                      )}
                      {m.status === "ACTIVE" && (
                        <>
                          <Button
                            size="sm"
                            variant="outline"
                            disabled={busy}
                            onClick={() => onExpand(expandedId === m.id ? null : m.id)}
                          >
                            {expandedId === m.id ? "Hide details" : "View mentee"}
                          </Button>
                          <Button size="sm" disabled={busy} onClick={() => onTransition(m.id, "COMPLETED")}>
                            Complete
                          </Button>
                          <Button size="sm" variant="outline" disabled={busy} onClick={() => onTransition(m.id, "ENDED")}>
                            End
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                  {m.status === "ACTIVE" && expandedId === m.id && <MenteeDetailsPanel mentorshipId={m.id} />}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

type BundleState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; bundle: MenteeProfileBundle };

function MenteeDetailsPanel({ mentorshipId }: { mentorshipId: string }) {
  const [state, setState] = useState<BundleState>({ status: "loading" });
  const [note, setNote] = useState("");
  const [noteSaving, setNoteSaving] = useState(false);
  const [noteError, setNoteError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    async function load() {
      try {
        const [bundle, existingNote] = await Promise.all([
          getMenteeProfile(mentorshipId),
          getMentorshipNote(mentorshipId),
        ]);
        if (cancelled) return;
        setState({ status: "ready", bundle });
        setNote(existingNote?.note ?? "");
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load this mentee's information.",
        });
      }
    }
    void load();
    return () => {
      cancelled = true;
    };
  }, [mentorshipId]);

  async function handleSaveNote() {
    setNoteSaving(true);
    setNoteError(null);
    try {
      await saveMentorshipNote(mentorshipId, note);
    } catch (err) {
      setNoteError(err instanceof ApiError ? err.message : "Could not save this note.");
    } finally {
      setNoteSaving(false);
    }
  }

  if (state.status === "loading") {
    return (
      <p className="flex items-center gap-2 border-t border-border/60 pt-4 text-sm text-muted-foreground" aria-busy="true">
        <Loader2 className="size-4 animate-spin" /> Loading mentee details…
      </p>
    );
  }

  if (state.status === "error") {
    return (
      <p className="flex items-center gap-1.5 border-t border-border/60 pt-4 text-sm text-destructive">
        <AlertCircle className="size-3.5 shrink-0" /> {state.message}
      </p>
    );
  }

  const { bundle } = state;

  return (
    <div className="flex flex-col gap-4 border-t border-border/60 pt-4">
      <div>
        <p className="font-medium">{bundle.full_name ?? bundle.username ?? bundle.email ?? "Mentee"}</p>
        {bundle.email && <p className="text-sm text-muted-foreground">{bundle.email}</p>}
      </div>

      <div className="text-sm">
        <p className="font-medium">Academic profile</p>
        <p className="text-muted-foreground">
          {bundle.academic_profile
            ? [
                bundle.academic_profile.degree,
                bundle.academic_profile.department,
                bundle.academic_profile.institution_name,
              ]
                .filter(Boolean)
                .join(" · ") || "No academic details on file yet."
            : "No academic profile on file yet."}
        </p>
      </div>

      <div className="text-sm">
        <p className="font-medium">Skills</p>
        {bundle.skills.length === 0 ? (
          <p className="text-muted-foreground">No skills on file yet.</p>
        ) : (
          <ul className="list-disc pl-5 text-muted-foreground">
            {bundle.skills.map((s) => (
              <li key={s.skill_id}>
                {s.proficiency_level}
                {s.is_verified ? " (verified)" : ""}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="text-sm">
        <p className="font-medium">Assessment results</p>
        {bundle.assessment_attempts.length === 0 ? (
          <p className="text-muted-foreground">No completed assessments yet.</p>
        ) : (
          <ul className="list-disc pl-5 text-muted-foreground">
            {bundle.assessment_attempts.map((a) => (
              <li key={a.id}>
                {a.status}
                {a.percentage !== null ? ` — ${a.percentage}%` : ""}
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="text-sm">
        <p className="font-medium">Portfolio</p>
        {bundle.projects.length === 0 && bundle.certifications.length === 0 ? (
          <p className="text-muted-foreground">No portfolio items yet.</p>
        ) : (
          <ul className="list-disc pl-5 text-muted-foreground">
            {bundle.projects.map((p) => (
              <li key={p.id}>{p.title}</li>
            ))}
            {bundle.certifications.map((c) => (
              <li key={c.id}>
                {c.name} ({c.issuer})
              </li>
            ))}
          </ul>
        )}
      </div>

      <div className="flex flex-col gap-1.5">
        <Label htmlFor={`mentorship-note-${mentorshipId}`}>Private note (visible only to you)</Label>
        <Textarea
          id={`mentorship-note-${mentorshipId}`}
          value={note}
          onChange={(e) => setNote(e.target.value)}
          rows={3}
        />
        {noteError && (
          <p className="flex items-center gap-1.5 text-sm text-destructive">
            <AlertCircle className="size-3.5 shrink-0" /> {noteError}
          </p>
        )}
        <div>
          <Button size="sm" disabled={noteSaving} onClick={() => void handleSaveNote()}>
            Save note
          </Button>
        </div>
      </div>
    </div>
  );
}
