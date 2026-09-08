"use client";

import { useEffect, useMemo, useState } from "react";
import { Contact, Plus, Search } from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import { ErrorState } from "@/components/common/error-state";
import { Loading } from "@/components/common/loading";
import { ApiError } from "@/lib/api";
import { getIndustryConnections } from "@/lib/institution/industry-connections";
import type { IndustryConnectionRow } from "@/types/institution-industry-connection";
import { CONTACT_TYPE_LABELS } from "@/types/institution-industry-connection";
import { IndustryConnectionForm } from "@/components/institution/industry-connections/industry-connection-form";

const ALL = "__all__";

type LoadState =
  | { status: "loading" }
  | { status: "error"; error: ApiError }
  | { status: "ready"; connections: IndustryConnectionRow[]; typeOptions: string[] };

/**
 * Institution Industry Connections directory (Phase 9): the TPO's own
 * record of named contact people at companies -- distinct from Phase
 * 8's Industry Partners (a company-level relationship tag) and from the
 * industry_collaborations proposal workflow. Never fabricates a "last
 * interaction" -- no such history is modeled anywhere in this schema.
 */
export function IndustryConnectionsList() {
  const [state, setState] = useState<LoadState>({ status: "loading" });
  const [reloadKey, setReloadKey] = useState(0);
  const [search, setSearch] = useState("");
  const [typeFilter, setTypeFilter] = useState(ALL);
  const [statusFilter, setStatusFilter] = useState<"all" | "active" | "inactive">("active");
  const [formOpen, setFormOpen] = useState(false);
  const [editing, setEditing] = useState<IndustryConnectionRow | undefined>(undefined);

  useEffect(() => {
    let cancelled = false;
    getIndustryConnections()
      .then(({ connections, type_options }) => {
        if (!cancelled) setState({ status: "ready", connections, typeOptions: type_options });
      })
      .catch((err) => {
        if (cancelled) return;
        setState({
          status: "error",
          error: err instanceof ApiError ? err : new ApiError(0, "Could not load your industry connections."),
        });
      });
    return () => {
      cancelled = true;
    };
  }, [reloadKey]);

  const filtered = useMemo(() => {
    if (state.status !== "ready") return [];
    let rows = state.connections;
    if (typeFilter !== ALL) rows = rows.filter((r) => r.contact_type === typeFilter);
    if (statusFilter !== "all") rows = rows.filter((r) => (statusFilter === "active" ? r.is_active : !r.is_active));
    const needle = search.trim().toLowerCase();
    if (needle) {
      rows = rows.filter(
        (r) => (r.company_name ?? "").toLowerCase().includes(needle) || r.contact_name.toLowerCase().includes(needle),
      );
    }
    return rows;
  }, [state, search, typeFilter, statusFilter]);

  function reload() {
    setState({ status: "loading" });
    setReloadKey((k) => k + 1);
  }

  function openCreate() {
    setEditing(undefined);
    setFormOpen(true);
  }

  function openEdit(connection: IndustryConnectionRow) {
    setEditing(connection);
    setFormOpen(true);
  }

  function handleSaved() {
    setFormOpen(false);
    reload();
  }

  const hasAny = state.status === "ready" && state.connections.length > 0;

  return (
    <div className="mx-auto max-w-6xl space-y-6">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <h1 className="text-xl font-semibold">Industry Connections</h1>
          <p className="text-sm text-muted-foreground">
            Your institution&apos;s own contact people at companies -- private records, separate from each
            company&apos;s public profile.
          </p>
        </div>
        <Button onClick={openCreate}>
          <Plus className="size-4" /> Add Contact
        </Button>
      </div>

      {state.status === "loading" ? <Loading label="Loading industry connections…" className="py-16" /> : null}

      {state.status === "error" ? (
        <ErrorState
          message={
            state.error.status === 401 ? "Your session has expired. Please sign in again." : state.error.message
          }
          onRetry={state.error.status !== 401 ? reload : undefined}
        />
      ) : null}

      {state.status === "ready" ? (
        <>
          {hasAny ? (
            <div className="flex flex-col gap-3 sm:flex-row sm:items-center">
              <div className="relative w-full sm:max-w-xs">
                <Search className="absolute top-1/2 left-2.5 size-4 -translate-y-1/2 text-muted-foreground" aria-hidden="true" />
                <Input
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                  placeholder="Search by company or contact name..."
                  className="pl-8"
                  aria-label="Search connections"
                />
              </div>
              <Select value={typeFilter} onValueChange={(v) => setTypeFilter(v ?? ALL)}>
                <SelectTrigger className="w-full sm:w-48" aria-label="Filter by connection type">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value={ALL}>All connection types</SelectItem>
                  {state.typeOptions.map((t) => (
                    <SelectItem key={t} value={t}>
                      {CONTACT_TYPE_LABELS[t] ?? t}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select value={statusFilter} onValueChange={(v) => setStatusFilter((v as typeof statusFilter) ?? "active")}>
                <SelectTrigger className="w-full sm:w-36" aria-label="Filter by status">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="active">Active</SelectItem>
                  <SelectItem value="inactive">Inactive</SelectItem>
                  <SelectItem value="all">All</SelectItem>
                </SelectContent>
              </Select>
            </div>
          ) : null}

          {!hasAny ? (
            <EmptyState
              icon={Contact}
              title="No industry connections yet"
              description="Add your first contact at a company to start tracking who your institution works with."
              actionLabel="Add Contact"
              onAction={openCreate}
            />
          ) : filtered.length === 0 ? (
            <EmptyState icon={Search} title="No connections match your filters" />
          ) : (
            <Card>
              <CardContent className="p-0">
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Company</TableHead>
                      <TableHead>Contact</TableHead>
                      <TableHead>Designation</TableHead>
                      <TableHead>Type</TableHead>
                      <TableHead>Email / Phone</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead className="text-right">Actions</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {filtered.map((c) => (
                      <TableRow key={c.id}>
                        <TableCell className="font-medium">{c.company_name ?? "Unknown company"}</TableCell>
                        <TableCell>{c.contact_name}</TableCell>
                        <TableCell className="text-muted-foreground">{c.designation ?? "—"}</TableCell>
                        <TableCell className="text-muted-foreground">
                          {CONTACT_TYPE_LABELS[c.contact_type] ?? c.contact_type}
                        </TableCell>
                        <TableCell className="text-muted-foreground">
                          {[c.email, c.phone].filter(Boolean).join(" · ") || "—"}
                        </TableCell>
                        <TableCell>
                          <Badge variant={c.is_active ? "default" : "secondary"}>
                            {c.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </TableCell>
                        <TableCell className="text-right">
                          <Button size="sm" variant="outline" onClick={() => openEdit(c)}>
                            Edit
                          </Button>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              </CardContent>
            </Card>
          )}
        </>
      ) : null}

      <IndustryConnectionForm
        key={editing?.id ?? "create"}
        open={formOpen}
        onOpenChange={setFormOpen}
        connection={editing}
        onSaved={handleSaved}
      />
    </div>
  );
}
