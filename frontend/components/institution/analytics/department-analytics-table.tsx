"use client";

import { useMemo, useState } from "react";
import Link from "next/link";
import { ArrowDown, ArrowUp, Building2 } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { EmptyState } from "@/components/common/empty-state";
import { cn } from "@/lib/utils";
import type { DepartmentAnalytics } from "@/types/institution-analytics-report";

type SortKey = "name" | "student_count" | "placed_count" | "placement_rate";

const SORT_LABELS: Record<SortKey, string> = {
  name: "Department",
  student_count: "Students",
  placed_count: "Placed",
  placement_rate: "Placement Rate",
};

/**
 * Department Performance (Phase 6, Part 7/8) -- these are the EXACT same
 * rows /institution/departments renders (institution_department_service.
 * list_departments, reused verbatim by the analytics endpoint), just
 * sortable here. Deliberately uses neutral "Highest placement rate" /
 * "Largest student population" language, never "best department" --
 * a small institution/department is not implicitly worse.
 */
export function DepartmentAnalyticsTable({ departments }: { departments: DepartmentAnalytics[] }) {
  const [sortKey, setSortKey] = useState<SortKey>("placement_rate");
  const [desc, setDesc] = useState(true);

  const sorted = useMemo(() => {
    const rows = [...departments];
    rows.sort((a, b) => {
      let cmp: number;
      if (sortKey === "name") {
        cmp = a.name.localeCompare(b.name);
      } else if (sortKey === "placement_rate") {
        const av = a.placement_rate ?? -1;
        const bv = b.placement_rate ?? -1;
        cmp = av - bv;
      } else {
        cmp = a[sortKey] - b[sortKey];
      }
      return desc ? -cmp : cmp;
    });
    return rows;
  }, [departments, sortKey, desc]);

  function toggleSort(key: SortKey) {
    if (key === sortKey) {
      setDesc((d) => !d);
    } else {
      setSortKey(key);
      setDesc(true);
    }
  }

  const highestRate = useMemo(
    () =>
      departments
        .filter((d) => d.placement_rate != null && d.student_count > 0)
        .sort((a, b) => (b.placement_rate ?? 0) - (a.placement_rate ?? 0))[0],
    [departments],
  );
  const largestPopulation = useMemo(
    () => [...departments].sort((a, b) => b.student_count - a.student_count)[0],
    [departments],
  );

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-base">Department Performance</CardTitle>
        <p className="text-xs text-muted-foreground">
          Institution-wide, never affected by this page&apos;s own filters -- the same rows as{" "}
          <Link href="/institution/departments" className="text-indigo-600 hover:underline dark:text-indigo-400">
            Departments
          </Link>
          .
        </p>
      </CardHeader>
      <CardContent className="space-y-4">
        {departments.length === 0 ? (
          <EmptyState
            icon={Building2}
            title="No department data yet"
            description="This appears once students are linked to your institution and assigned to departments."
          />
        ) : (
          <>
            {(highestRate || largestPopulation) && (
              <div className="flex flex-wrap gap-2 text-xs text-muted-foreground">
                {highestRate ? (
                  <span className="rounded-full bg-emerald-500/10 px-2.5 py-1 text-emerald-700 dark:text-emerald-400">
                    Highest placement rate: {highestRate.name} ({highestRate.placement_rate}%)
                  </span>
                ) : null}
                {largestPopulation && largestPopulation.student_count > 0 ? (
                  <span className="rounded-full bg-indigo-500/10 px-2.5 py-1 text-indigo-700 dark:text-indigo-400">
                    Largest student population: {largestPopulation.name} ({largestPopulation.student_count})
                  </span>
                ) : null}
              </div>
            )}

            <Table>
              <TableHeader>
                <TableRow>
                  {(Object.keys(SORT_LABELS) as SortKey[]).map((key) => (
                    <TableHead
                      key={key}
                      className={cn("cursor-pointer select-none", key !== "name" && "text-right")}
                      onClick={() => toggleSort(key)}
                    >
                      <span className="inline-flex items-center gap-1">
                        {SORT_LABELS[key]}
                        {sortKey === key ? (
                          desc ? (
                            <ArrowDown className="size-3" aria-hidden="true" />
                          ) : (
                            <ArrowUp className="size-3" aria-hidden="true" />
                          )
                        ) : null}
                      </span>
                    </TableHead>
                  ))}
                  <TableHead className="text-right">No Applications</TableHead>
                  <TableHead className="text-right">Internship Selected</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sorted.map((d) => (
                  <TableRow key={d.id}>
                    <TableCell className="font-medium">
                      <Link href={`/institution/departments/${d.id}`} className="hover:underline">
                        {d.name}
                      </Link>
                      {!d.is_active ? <span className="ml-1.5 text-xs text-muted-foreground">(inactive)</span> : null}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{d.student_count}</TableCell>
                    <TableCell className="text-right tabular-nums">{d.placed_count}</TableCell>
                    <TableCell className="text-right tabular-nums">
                      {d.student_count === 0 ? "N/A" : d.placement_rate != null ? `${d.placement_rate}%` : "—"}
                    </TableCell>
                    <TableCell className="text-right tabular-nums">{d.no_applications_count}</TableCell>
                    <TableCell className="text-right tabular-nums">{d.internship_selected_count}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </>
        )}
      </CardContent>
    </Card>
  );
}
