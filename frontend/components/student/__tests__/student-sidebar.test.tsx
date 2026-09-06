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

  it("links My Institution to /student/institution", () => {
    render(<StudentSidebar />);

    expect(screen.getByRole("link", { name: /my institution/i })).toHaveAttribute(
      "href",
      "/student/institution",
    );
  });

  it("links My Internships to /student/my-internships", () => {
    render(<StudentSidebar />);

    expect(screen.getByRole("link", { name: /my internships/i })).toHaveAttribute(
      "href",
      "/student/my-internships",
    );
  });
});
