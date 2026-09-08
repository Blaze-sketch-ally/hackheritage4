import { describe, expect, it } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";
import { DepartmentAnalyticsTable } from "@/components/institution/analytics/department-analytics-table";
import type { DepartmentAnalytics } from "@/types/institution-analytics-report";

const DEPARTMENTS: DepartmentAnalytics[] = [
  {
    id: "d1",
    name: "CSE",
    code: "CSE",
    is_active: true,
    student_count: 60,
    placed_count: 30,
    unplaced_count: 20,
    no_applications_count: 10,
    placement_rate: 50,
    internship_selected_count: 4,
  },
  {
    id: "d2",
    name: "ECE",
    code: "ECE",
    is_active: true,
    student_count: 40,
    placed_count: 30,
    unplaced_count: 5,
    no_applications_count: 5,
    placement_rate: 75,
    internship_selected_count: 2,
  },
  {
    id: "d3",
    name: "Mechanical",
    code: "ME",
    is_active: true,
    student_count: 0,
    placed_count: 0,
    unplaced_count: 0,
    no_applications_count: 0,
    placement_rate: null,
    internship_selected_count: 0,
  },
];

describe("DepartmentAnalyticsTable", () => {
  it("renders an empty state when there are no departments", () => {
    render(<DepartmentAnalyticsTable departments={[]} />);
    expect(screen.getByText("No department data yet")).toBeInTheDocument();
  });

  it("shows N/A instead of a fabricated 0% for a department with zero students", () => {
    render(<DepartmentAnalyticsTable departments={DEPARTMENTS} />);
    const row = screen.getByText("Mechanical").closest("tr");
    expect(row).not.toBeNull();
    expect(row).toHaveTextContent("N/A");
  });

  it("highlights the highest placement rate and largest student population using neutral language", () => {
    render(<DepartmentAnalyticsTable departments={DEPARTMENTS} />);
    expect(screen.getByText(/Highest placement rate: ECE/i)).toBeInTheDocument();
    expect(screen.getByText(/Largest student population: CSE/i)).toBeInTheDocument();
    expect(screen.queryByText(/best department/i)).not.toBeInTheDocument();
  });

  it("sorts by column when a header is clicked", async () => {
    const { container } = render(<DepartmentAnalyticsTable departments={DEPARTMENTS} />);
    const nameHeader = screen.getByText("Department");
    // First click switches sort to name (descending by default for a new column).
    fireEvent.click(nameHeader);
    // Second click flips the same column to ascending (A -> Z).
    fireEvent.click(nameHeader);
    const firstRowName = container.querySelectorAll("tbody tr")[0]?.textContent ?? "";
    expect(firstRowName).toContain("CSE");
  });
});
