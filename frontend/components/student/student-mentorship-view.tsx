"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Loader2, RefreshCw } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { ApiError } from "@/lib/api";
import { listMyMentorships, requestMentorship, updateMentorshipStatus } from "@/lib/student/mentorships";
import {
  MENTORSHIP_STATUS_LABELS,
  type FacultyStudentMentorship,
  type MentorshipStatus,
} from "@/types/faculty-mentorship";

/**
 * Phase F4.2 -- the Student-side mirror of FacultyMentorshipView. No
 * capability concept here (faculty_mentor only gates the Faculty
 * participant) and no mentee-data bundle (a Student already has full
 * access to their own data through the existing Student-facing pages).
 */

type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; mentorships: FacultyStudentMentorship[] };

type TransitionStatus = Extract<
  MentorshipStatus,
  "ACCEPTED" | "DECLINED" | "WITHDRAWN" | "ACTIVE" | "COMPLETED" | "ENDED"
>;

export function StudentMentorshipView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [busyId, setBusyId] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

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

  return (
    <div className="flex flex-col gap-6">
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Request a mentor</CardTitle>
        </CardHeader>
        <CardContent className="flex flex-col gap-3">
          <div className="grid gap-3 sm:grid-cols-2">
            <div className="flex flex-col gap-1.5">
              <Label htmlFor="mentorship-faculty-id">Faculty ID</Label>
              <Input
                id="mentorship-faculty-id"
                value={targetId}
                onChange={(e) => setTargetId(e.target.value)}
                placeholder="The faculty member's account id"
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
            <Button size="sm" disabled={requesting || !targetId.trim()} onClick={() => void handleRequest()}>
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

      {mentorships.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            You don&apos;t have any mentorships yet.
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-3">
          {mentorships.map((m) => {
            const busy = busyId === m.id;
            const iRequested = m.requested_by === m.student_id;
            return (
              <Card key={m.id}>
                <CardContent className="flex flex-col gap-2 py-4 sm:flex-row sm:items-center sm:justify-between">
                  <div className="min-w-0">
                    <p className="font-medium">Faculty #{m.faculty_id.slice(0, 8)}</p>
                    {m.focus_area && <p className="text-sm text-muted-foreground">{m.focus_area}</p>}
                  </div>
                  <div className="flex shrink-0 flex-wrap items-center gap-1.5">
                    <Badge variant="outline">{MENTORSHIP_STATUS_LABELS[m.status]}</Badge>
                    {m.status === "REQUESTED" && iRequested && (
                      <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleTransition(m.id, "WITHDRAWN")}>
                        Withdraw
                      </Button>
                    )}
                    {m.status === "REQUESTED" && !iRequested && (
                      <>
                        <Button size="sm" disabled={busy} onClick={() => void handleTransition(m.id, "ACCEPTED")}>
                          Accept
                        </Button>
                        <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleTransition(m.id, "DECLINED")}>
                          Decline
                        </Button>
                      </>
                    )}
                    {m.status === "ACCEPTED" && (
                      <Button size="sm" disabled={busy} onClick={() => void handleTransition(m.id, "ACTIVE")}>
                        Activate
                      </Button>
                    )}
                    {m.status === "ACTIVE" && (
                      <>
                        <Button size="sm" disabled={busy} onClick={() => void handleTransition(m.id, "COMPLETED")}>
                          Complete
                        </Button>
                        <Button size="sm" variant="outline" disabled={busy} onClick={() => void handleTransition(m.id, "ENDED")}>
                          End
                        </Button>
                      </>
                    )}
                  </div>
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
