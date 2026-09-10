import { toCsv } from "@/lib/csv-export";
import type { InstitutionReportResponse } from "@/types/institution-reports";

/** Maps each report's own primary table to a flat CSV -- Phase 11, Step
 * 15. Returns null when the report (or its data) isn't loaded yet, or
 * has nothing to export. Only ever exports the SAME rows already
 * rendered in ReportOutput -- never a second, differently-computed
 * dataset. */
export function reportToCsv(report: InstitutionReportResponse): string | null {
  switch (report.report_type) {
    case "PLACEMENT":
      if (!report.placement) return null;
      return toCsv(report.placement.department_breakdown, [
        { key: "department", header: "Department" },
        { key: "student_count", header: "Students" },
        { key: "placed_count", header: "Placed" },
        { key: "placement_rate", header: "Placement Rate (%)" },
      ]);
    case "INTERNSHIP":
      if (!report.internship) return null;
      return toCsv(report.internship.company_breakdown, [
        { key: "company_name", header: "Company" },
        { key: "opportunities", header: "Opportunities" },
        { key: "applicants", header: "Applicants" },
        { key: "selected", header: "Selected" },
        { key: "completed", header: "Completed" },
      ]);
    case "STUDENT":
      if (!report.student) return null;
      return toCsv(report.student.students, [
        { key: "full_name", header: "Name" },
        { key: "username", header: "Username" },
        { key: "department", header: "Department" },
        { key: "batch", header: "Batch" },
        { key: "cgpa", header: "CGPA" },
        { key: "placement_status", header: "Placement Status" },
        { key: "internship_status", header: "Internship Status" },
        { key: "top_skills", header: "Top Skills" },
      ]);
    case "DEPARTMENT":
      if (!report.department) return null;
      return toCsv(report.department.departments, [
        { key: "name", header: "Department" },
        { key: "code", header: "Code" },
        { key: "student_count", header: "Students" },
        { key: "average_cgpa", header: "Average CGPA" },
        { key: "placed_count", header: "Placed" },
        { key: "placement_rate", header: "Placement Rate (%)" },
        { key: "internship_selected_count", header: "Internship Selected" },
        { key: "applications_total", header: "Applications" },
      ]);
    case "INDUSTRY":
      if (!report.industry) return null;
      return toCsv(report.industry.companies, [
        { key: "company_name", header: "Company" },
        { key: "relationship_type", header: "Relationship Type" },
        { key: "relationship_status", header: "Relationship Status" },
        { key: "jobs_opportunities", header: "Jobs" },
        { key: "internship_opportunities", header: "Internships" },
        { key: "placement_drives_count", header: "Drives" },
        { key: "students_selected", header: "Students Selected" },
        { key: "connections_count", header: "Connections" },
        { key: "events_count", header: "Events" },
        { key: "collaborations_count", header: "Collaborations" },
      ]);
    case "EVENTS":
      if (!report.events) return null;
      return toCsv(report.events.events, [
        { key: "title", header: "Title" },
        { key: "event_type", header: "Type" },
        { key: "status", header: "Status" },
        { key: "company_name", header: "Company" },
        { key: "start_at", header: "Start" },
        { key: "target_department_names", header: "Departments" },
      ]);
    case "COLLABORATION":
      if (!report.collaboration) return null;
      return toCsv(report.collaboration.collaborations, [
        { key: "title", header: "Title" },
        { key: "company_name", header: "Company" },
        { key: "status", header: "Status" },
        { key: "created_at", header: "Created" },
        { key: "updated_at", header: "Updated" },
      ]);
    default:
      return null;
  }
}
