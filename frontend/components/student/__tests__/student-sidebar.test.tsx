import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({ usePathname: () => "/student/dashboard" }));

import { StudentSidebar } from "@/components/student/student-sidebar";

describe("StudentSidebar", () => {
  it("links Skill Gap Analysis to /student/skill-gap", () => {
    render(<StudentSidebar />);

    expect(screen.getByRole("link", { name: /skill gap analysis/i })).toHaveAttribute(
      "href",
      "/student/skill-gap",
    );
  });

  it("links My Internships to /student/my-internships", () => {
    render(<StudentSidebar />);

    expect(screen.getByRole("link", { name: /my internships/i })).toHaveAttribute(
      "href",
      "/student/my-internships",
    );
  });

  it("hides the Job Training item by default (no enrollment)", () => {
    render(<StudentSidebar />);
    expect(screen.queryByRole("link", { name: /job training/i })).not.toBeInTheDocument();
  });

  it("hides the Job Training item when hasJobTraining is false", () => {
    render(<StudentSidebar hasJobTraining={false} />);
    expect(screen.queryByRole("link", { name: /job training/i })).not.toBeInTheDocument();
  });

  it("shows the Job Training item linking to /student/job-training when hasJobTraining is true", () => {
    render(<StudentSidebar hasJobTraining />);
    expect(screen.getByRole("link", { name: /job training/i })).toHaveAttribute(
      "href",
      "/student/job-training",
    );
  });

  it("keeps Job Training distinct from the universal Learning & Courses item", () => {
    render(<StudentSidebar hasJobTraining />);
    expect(screen.getByRole("link", { name: /learning & courses/i })).toHaveAttribute(
      "href",
      "/student/learning",
    );
    expect(screen.getByRole("link", { name: /job training/i })).toHaveAttribute(
      "href",
      "/student/job-training",
    );
  });
});
