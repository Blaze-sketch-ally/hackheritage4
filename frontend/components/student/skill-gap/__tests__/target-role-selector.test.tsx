import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import { TargetRoleSelector } from "@/components/student/skill-gap/target-role-selector";
import type { JobRole } from "@/types/skill-gap";

/** Only covers rendering/labels, not the @base-ui/react Select popup's
 * own open/select interaction -- that path is exercised via a live
 * browser walkthrough instead (not reliably testable under jsdom for
 * this Select implementation). SkillGapView's onSelect/onClear wiring is
 * covered separately in skill-gap-view.test.tsx with this component
 * stubbed out. */
function role(overrides: Partial<JobRole> = {}): JobRole {
  return {
    id: "role-backend",
    name: "Backend Developer",
    description: null,
    category: "Engineering",
    is_active: true,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("TargetRoleSelector", () => {
  it("shows 'No target job role selected.' with no Clear button when nothing is selected", () => {
    render(
      <TargetRoleSelector jobRoles={[role()]} selectedJobRoleId={null} saving={false} onSelect={vi.fn()} onClear={vi.fn()} />,
    );

    expect(screen.getByText("No target job role selected.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Clear" })).not.toBeInTheDocument();
  });

  it("shows the selected role's name and a Clear button once a target role is set", () => {
    render(
      <TargetRoleSelector
        jobRoles={[role()]}
        selectedJobRoleId="role-backend"
        saving={false}
        onSelect={vi.fn()}
        onClear={vi.fn()}
      />,
    );

    expect(screen.getByText("Target Role: Backend Developer")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Clear" })).toBeInTheDocument();
  });

  it("shows 'No job roles are currently available.' when the catalog is empty", () => {
    render(<TargetRoleSelector jobRoles={[]} selectedJobRoleId={null} saving={false} onSelect={vi.fn()} onClear={vi.fn()} />);

    expect(screen.getByText("No job roles are currently available.")).toBeInTheDocument();
  });
});
