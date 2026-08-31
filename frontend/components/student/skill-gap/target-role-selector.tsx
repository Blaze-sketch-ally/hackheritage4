"use client";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import type { JobRole } from "@/types/skill-gap";

/** The target-role picker at the top of the Skill Gap page. Options come
 * directly from GET /job-roles (never hardcoded); selecting/clearing
 * writes through PUT/DELETE /student/target-job-role and lets the parent
 * refetch the analysis -- this component holds no analysis state itself. */
export function TargetRoleSelector({
  jobRoles,
  selectedJobRoleId,
  saving,
  onSelect,
  onClear,
}: {
  jobRoles: JobRole[];
  selectedJobRoleId: string | null;
  saving: boolean;
  onSelect: (jobRoleId: string) => void;
  onClear: () => void;
}) {
  const selectedRole = jobRoles.find((role) => role.id === selectedJobRoleId) ?? null;
  const items = Object.fromEntries(jobRoles.map((role) => [role.id, role.name]));

  return (
    <Card>
      <CardContent className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-sm font-medium">Target Job Role</p>
          <p className="text-xs text-muted-foreground">
            {selectedRole ? `Target Role: ${selectedRole.name}` : "No target job role selected."}
          </p>
        </div>

        {jobRoles.length === 0 ? (
          <p className="text-sm text-muted-foreground">No job roles are currently available.</p>
        ) : (
          <div className="flex items-center gap-2">
            <Select
              value={selectedJobRoleId ?? ""}
              onValueChange={(value) => value && onSelect(value as string)}
              disabled={saving}
              items={items}
            >
              <SelectTrigger className="w-56">
                <SelectValue placeholder="Select a job role" />
              </SelectTrigger>
              <SelectContent>
                {jobRoles.map((role) => (
                  <SelectItem key={role.id} value={role.id}>
                    {role.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            {selectedJobRoleId ? (
              <Button variant="outline" size="sm" onClick={onClear} disabled={saving}>
                Clear
              </Button>
            ) : null}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
