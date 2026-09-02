"use client";

import { useEffect, useState } from "react";
import { AlertCircle, Loader2 } from "lucide-react";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { ApiError } from "@/lib/api";
import { ASSESSMENT_CAPABILITIES, type AssessmentCapability } from "@/lib/faculty/capabilities";
import {
  grantAssessmentCapability,
  listFacultyAssessmentPermissions,
  setAssessmentPermissionStatus,
} from "@/lib/admin/faculty-permissions";
import {
  grantMentorCapability,
  listFacultyMentorPermissions,
  setMentorPermissionStatus,
  type FacultyMentorPermissionAdmin,
  type MentorPermissionStatus,
} from "@/lib/admin/mentor-permissions";
import type { FacultyWithPermissions, PermissionStatus } from "@/types/faculty-permission";

/**
 * ADMIN-only management surface over Faculty assessment capabilities.
 * This is a UI convenience only -- every action here is re-authorized by
 * the backend (require_admin) and, independently, by each admin_* RPC's
 * own is_admin() check. Nothing here decides who is allowed to do what;
 * it only calls the already-secured API and reflects what it returns.
 */
type LoadState =
  | { status: "loading" }
  | { status: "error"; message: string }
  | { status: "ready"; faculty: FacultyWithPermissions[] };

export function FacultyPermissionsView() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [mentorPermissions, setMentorPermissions] = useState<Map<string, FacultyMentorPermissionAdmin>>(new Map());
  const [reloadKey, setReloadKey] = useState(0);
  const [busyKey, setBusyKey] = useState<string | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      try {
        const [{ faculty }, { faculty: mentorFaculty }] = await Promise.all([
          listFacultyAssessmentPermissions(),
          listFacultyMentorPermissions(),
        ]);
        if (cancelled) return;
        setState({ status: "ready", faculty });
        setMentorPermissions(
          new Map(mentorFaculty.filter((f) => f.permission !== null).map((f) => [f.faculty_id, f.permission!])),
        );
      } catch (err) {
        if (cancelled) return;
        setState({
          status: "error",
          message: err instanceof ApiError ? err.message : "Could not load Faculty permissions.",
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  function retry() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  async function refresh() {
    const [{ faculty }, { faculty: mentorFaculty }] = await Promise.all([
      listFacultyAssessmentPermissions(),
      listFacultyMentorPermissions(),
    ]);
    setState({ status: "ready", faculty });
    setMentorPermissions(
      new Map(mentorFaculty.filter((f) => f.permission !== null).map((f) => [f.faculty_id, f.permission!])),
    );
  }

  async function handleGrant(facultyId: string, capability: AssessmentCapability) {
    const key = `${facultyId}:${capability}:grant`;
    setBusyKey(key);
    setActionError(null);
    try {
      await grantAssessmentCapability(facultyId, capability);
      await refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not grant the capability.");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleStatusChange(permissionId: string, status: PermissionStatus) {
    setBusyKey(permissionId);
    setActionError(null);
    try {
      await setAssessmentPermissionStatus(permissionId, status);
      await refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not update the permission status.");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleGrantMentor(facultyId: string) {
    const key = `${facultyId}:mentor:grant`;
    setBusyKey(key);
    setActionError(null);
    try {
      await grantMentorCapability(facultyId);
      await refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not grant the mentor capability.");
    } finally {
      setBusyKey(null);
    }
  }

  async function handleMentorStatusChange(permissionId: string, status: MentorPermissionStatus) {
    setBusyKey(permissionId);
    setActionError(null);
    try {
      await setMentorPermissionStatus(permissionId, status);
      await refresh();
    } catch (err) {
      setActionError(err instanceof ApiError ? err.message : "Could not update the mentor permission status.");
    } finally {
      setBusyKey(null);
    }
  }

  if (state.status === "loading") {
    return (
      <Card>
        <CardContent className="flex items-center justify-center gap-2 py-10 text-muted-foreground" aria-busy="true">
          <Loader2 className="size-5 animate-spin" /> Loading Faculty…
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
          <Button size="sm" onClick={retry}>
            Try again
          </Button>
        </CardContent>
      </Card>
    );
  }

  const { faculty } = state;

  return (
    <div className="flex flex-col gap-4">
      {actionError && (
        <p className="flex items-center gap-1.5 text-sm text-destructive">
          <AlertCircle className="size-3.5 shrink-0" /> {actionError}
        </p>
      )}

      {faculty.length === 0 ? (
        <Card>
          <CardContent className="py-10 text-center text-sm text-muted-foreground">
            No Faculty accounts found.
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-4">
          {faculty.map((member) => {
            const granted = new Map(member.permissions.map((p) => [p.capability, p]));
            return (
              <Card key={member.faculty_id}>
                <CardContent className="flex flex-col gap-3 py-4">
                  <div>
                    <p className="font-medium">{member.full_name ?? member.username ?? member.email}</p>
                    <p className="text-sm text-muted-foreground">{member.email}</p>
                  </div>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Capability</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Expires</TableHead>
                        <TableHead className="text-right">Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {ASSESSMENT_CAPABILITIES.map((capability) => {
                        const permission = granted.get(capability);
                        const rowBusyKey = permission ? permission.permission_id : `${member.faculty_id}:${capability}:grant`;
                        const busy = busyKey === rowBusyKey;
                        return (
                          <TableRow key={capability}>
                            <TableCell className="font-mono text-xs">{capability}</TableCell>
                            <TableCell>
                              <StatusBadge status={permission?.status ?? null} />
                            </TableCell>
                            <TableCell className="text-muted-foreground">
                              {permission?.expires_at ? new Date(permission.expires_at).toLocaleDateString() : "—"}
                            </TableCell>
                            <TableCell className="text-right">
                              <div className="flex justify-end gap-1.5">
                                {!permission || permission.status !== "GRANTED" ? (
                                  <Button
                                    size="sm"
                                    variant="outline"
                                    disabled={busy}
                                    onClick={() => void handleGrant(member.faculty_id, capability)}
                                  >
                                    Grant
                                  </Button>
                                ) : (
                                  <>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      disabled={busy}
                                      onClick={() => void handleStatusChange(permission.permission_id, "SUSPENDED")}
                                    >
                                      Suspend
                                    </Button>
                                    <Button
                                      size="sm"
                                      variant="outline"
                                      disabled={busy}
                                      onClick={() => void handleStatusChange(permission.permission_id, "REVOKED")}
                                    >
                                      Revoke
                                    </Button>
                                  </>
                                )}
                                {permission && permission.status === "SUSPENDED" && (
                                  <Button
                                    size="sm"
                                    disabled={busy}
                                    onClick={() => void handleStatusChange(permission.permission_id, "GRANTED")}
                                  >
                                    Reinstate
                                  </Button>
                                )}
                              </div>
                            </TableCell>
                          </TableRow>
                        );
                      })}
                    </TableBody>
                  </Table>
                  <MentorCapabilityRow
                    facultyId={member.faculty_id}
                    permission={mentorPermissions.get(member.faculty_id) ?? null}
                    busyKey={busyKey}
                    onGrant={handleGrantMentor}
                    onStatusChange={handleMentorStatusChange}
                  />
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}

function StatusBadge({ status }: { status: PermissionStatus | null }) {
  if (status === null) return <Badge variant="secondary">Not granted</Badge>;
  if (status === "GRANTED") {
    return <Badge className="bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500">Granted</Badge>;
  }
  if (status === "SUSPENDED") return <Badge variant="outline">Suspended</Badge>;
  if (status === "REVOKED") return <Badge variant="destructive">Revoked</Badge>;
  return <Badge variant="secondary">Expired</Badge>;
}

/**
 * Phase F4.2 -- the separate faculty_mentor capability. Deliberately its
 * own small row, not merged into the ASSESSMENT_CAPABILITIES table above
 * -- assessment and mentorship are two independent trust axes with no
 * shared status enum (mentor has no EXPIRED state) or shared metadata
 * (no expires_at).
 */
function MentorCapabilityRow({
  facultyId,
  permission,
  busyKey,
  onGrant,
  onStatusChange,
}: {
  facultyId: string;
  permission: FacultyMentorPermissionAdmin | null;
  busyKey: string | null;
  onGrant: (facultyId: string) => void;
  onStatusChange: (permissionId: string, status: MentorPermissionStatus) => void;
}) {
  const rowBusyKey = permission ? permission.permission_id : `${facultyId}:mentor:grant`;
  const busy = busyKey === rowBusyKey;

  return (
    <div className="flex items-center justify-between rounded-lg border border-border/60 px-3 py-2">
      <div className="flex items-center gap-2">
        <span className="font-mono text-xs">faculty_mentor</span>
        <MentorStatusBadge status={permission?.status ?? null} />
      </div>
      <div className="flex gap-1.5">
        {!permission || permission.status !== "GRANTED" ? (
          <Button size="sm" variant="outline" disabled={busy} onClick={() => onGrant(facultyId)}>
            Grant
          </Button>
        ) : (
          <>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => onStatusChange(permission.permission_id, "SUSPENDED")}
            >
              Suspend
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={busy}
              onClick={() => onStatusChange(permission.permission_id, "REVOKED")}
            >
              Revoke
            </Button>
          </>
        )}
        {permission && permission.status === "SUSPENDED" && (
          <Button size="sm" disabled={busy} onClick={() => onStatusChange(permission.permission_id, "GRANTED")}>
            Reinstate
          </Button>
        )}
      </div>
    </div>
  );
}

function MentorStatusBadge({ status }: { status: MentorPermissionStatus | null }) {
  if (status === null) return <Badge variant="secondary">Not granted</Badge>;
  if (status === "GRANTED") {
    return <Badge className="bg-emerald-600 text-white hover:bg-emerald-600/90 dark:bg-emerald-500">Granted</Badge>;
  }
  if (status === "SUSPENDED") return <Badge variant="outline">Suspended</Badge>;
  return <Badge variant="destructive">Revoked</Badge>;
}
