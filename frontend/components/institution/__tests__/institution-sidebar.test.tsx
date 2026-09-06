import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({ usePathname: () => "/institution/dashboard" }));

import { InstitutionSidebar } from "@/components/institution/institution-sidebar";

describe("InstitutionSidebar", () => {
  it("links Dashboard to /institution/dashboard", () => {
    render(<InstitutionSidebar />);

    expect(screen.getByRole("link", { name: /dashboard/i })).toHaveAttribute(
      "href",
      "/institution/dashboard",
    );
  });

  it("exposes the shared Institution routes, including Collaborations", () => {
    render(<InstitutionSidebar />);

    expect(screen.getByRole("link", { name: /collaborations/i })).toHaveAttribute(
      "href",
      "/institution/collaborations",
    );
    expect(screen.getByRole("link", { name: /students/i })).toHaveAttribute(
      "href",
      "/institution/students",
    );
  });

  it("links Skill Gaps to /institution/skill-gaps and no longer shows Assessments", () => {
    render(<InstitutionSidebar />);

    expect(screen.getByRole("link", { name: /skill gaps/i })).toHaveAttribute(
      "href",
      "/institution/skill-gaps",
    );
    expect(screen.queryByRole("link", { name: /assessments/i })).not.toBeInTheDocument();
  });
});
