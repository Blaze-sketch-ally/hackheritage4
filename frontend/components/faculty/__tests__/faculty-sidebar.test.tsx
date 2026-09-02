import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

vi.mock("next/navigation", () => ({
  usePathname: () => "/faculty/dashboard",
}));

import { FacultySidebar } from "@/components/faculty/faculty-sidebar";

describe("FacultySidebar", () => {
  it("links every implemented route as a real navigable link", () => {
    render(<FacultySidebar />);

    for (const [name, href] of [
      ["Dashboard", "/faculty/dashboard"],
      ["Overview", "/faculty/assessment-studio"],
      ["Question Bank", "/faculty/questions"],
      ["Assessment Blueprints", "/faculty/blueprint"],
      ["Opportunities", "/faculty/opportunities"],
      ["Applications", "/faculty/applications"],
      ["Mentorship", "/faculty/mentorship"],
      ["Profile", "/faculty/profile"],
      ["Settings", "/faculty/settings"],
    ] as const) {
      expect(screen.getByRole("link", { name })).toHaveAttribute("href", href);
    }
  });

  it("shows not-yet-implemented Faculty features as disabled 'Soon' items, not fake links", () => {
    render(<FacultySidebar />);

    for (const label of [
      "Research",
      "Consultancy",
      "FDPs",
      "Workshops",
      "Collaborations",
      "Calendar",
      "Internships",
    ]) {
      expect(screen.queryByRole("link", { name: label })).not.toBeInTheDocument();
      const row = screen.getByText(label).closest("div");
      expect(row).toHaveTextContent("Soon");
    }
  });
});
