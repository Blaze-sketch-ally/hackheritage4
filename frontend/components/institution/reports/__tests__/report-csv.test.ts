import { describe, expect, it } from "vitest";
import { reportToCsv } from "@/components/institution/reports/report-csv";
import type { InstitutionReportResponse } from "@/types/institution-reports";

const FILTERS = {
  department_id: null,
  batch: null,
  company_id: null,
  status: null,
  event_type: null,
  collaboration_status: null,
  date_from: null,
  date_to: null,
};

function envelope(overrides: Partial<InstitutionReportResponse>): InstitutionReportResponse {
  return {
    report_type: "PLACEMENT",
    institution_name: null,
    generated_at: "2026-01-01T00:00:00Z",
    filters_applied: FILTERS,
    ...overrides,
  };
}

describe("reportToCsv", () => {
  it("exports the placement report's department breakdown", () => {
    const csv = reportToCsv(
      envelope({
        report_type: "PLACEMENT",
        placement: {
          summary: {
            total_students: 1,
            students_with_applications: 1,
            students_selected: 1,
            placement_rate: 100,
            companies_involved: 1,
            active_placement_drives: 0,
          },
          department_breakdown: [{ department_id: "d1", department: "CSE", student_count: 10, placed_count: 4, placement_rate: 40 }],
          company_breakdown: [],
          status_breakdown: [],
          note: "note",
        },
      }),
    );
    expect(csv).toContain("Department,Students,Placed,Placement Rate (%)");
    expect(csv).toContain("CSE,10,4,40");
  });

  it("returns null when the report's data is not yet populated", () => {
    expect(reportToCsv(envelope({ report_type: "PLACEMENT" }))).toBeNull();
  });

  it("exports the student report's roster", () => {
    const csv = reportToCsv(
      envelope({
        report_type: "STUDENT",
        student: {
          students: [
            { full_name: "Ada Lovelace", username: "ada", department: "CSE", batch: 2026, cgpa: 9.1,
              placement_status: "PLACED", internship_status: "NONE", top_skills: ["Python", "SQL"] },
          ],
          total: 1,
          page: 1,
          page_size: 100,
          summary: {},
          note: "note",
        },
      }),
    );
    expect(csv).toContain("Name,Username,Department,Batch,CGPA,Placement Status,Internship Status,Top Skills");
    expect(csv).toContain("Ada Lovelace,ada,CSE,2026,9.1,PLACED,NONE,Python; SQL");
  });

  it("returns null for an unrecognized report type", () => {
    // @ts-expect-error -- deliberately invalid report_type to test the fallback branch
    expect(reportToCsv(envelope({ report_type: "NOT_A_TYPE" }))).toBeNull();
  });
});
