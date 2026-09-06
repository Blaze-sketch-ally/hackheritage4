import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { InternshipForm } from "@/components/industry/opportunity-form";
import type { CatalogSkill } from "@/lib/industry/skills";
import type { Internship } from "@/types/internship";

const catalog: CatalogSkill[] = [
  { id: "s1", name: "Python", category_name: "Programming", description: null },
  { id: "s2", name: "SQL", category_name: "Data", description: null },
];

function existing(): Internship {
  return {
    id: "int-1",
    industry_id: "industry-1",
    title: "Backend Intern",
    description: "Work on APIs.",
    location: "Pune",
    work_mode: "HYBRID",
    duration_months: 6,
    stipend_amount: 15000,
    stipend_currency: "INR",
    openings: 2,
    eligibility_criteria: null,
    application_deadline: "2026-12-01",
    start_date: null,
    status: "DRAFT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    skills: [
      {
        skill_id: "s1",
        skill_name: "Python",
        category_name: "Programming",
        required_level: "Advanced",
        importance: "CORE",
      },
    ],
  };
}

describe("InternshipForm", () => {
  it("renders the section cards and a Save Draft action in create mode", () => {
    render(
      <InternshipForm
        mode="create"
        catalog={catalog}
        submitting={false}
        error={null}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText("Basic Information")).toBeInTheDocument();
    expect(screen.getByText("Compensation")).toBeInTheDocument();
    expect(screen.getByText("Required Skills")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Draft" })).toBeInTheDocument();
  });

  it("blocks submit and shows errors when title/description are empty", async () => {
    const onSubmit = vi.fn();
    render(
      <InternshipForm
        mode="create"
        catalog={catalog}
        submitting={false}
        error={null}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(screen.getByText("A title is required.")).toBeInTheDocument();
    expect(screen.getByText("A description is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects an out-of-range duration", async () => {
    const onSubmit = vi.fn();
    render(
      <InternshipForm
        mode="create"
        catalog={catalog}
        submitting={false}
        error={null}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    await userEvent.type(screen.getByLabelText("Title"), "Backend Intern");
    await userEvent.type(screen.getByLabelText("Description"), "Do backend things.");
    await userEvent.type(screen.getByLabelText("Duration (months)"), "40");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(screen.getByText(/between 1 and 24/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a normalised payload from a valid create form", async () => {
    const onSubmit = vi.fn();
    render(
      <InternshipForm
        mode="create"
        catalog={catalog}
        submitting={false}
        error={null}
        onSubmit={onSubmit}
        onCancel={vi.fn()}
      />,
    );

    await userEvent.type(screen.getByLabelText("Title"), "  Backend Intern  ");
    await userEvent.type(screen.getByLabelText("Description"), "Do backend things.");
    await userEvent.type(screen.getByLabelText("Duration (months)"), "6");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.title).toBe("Backend Intern");
    expect(payload.duration_months).toBe(6);
    expect(payload.location).toBeNull();
    expect(payload.skills).toEqual([]);
  });

  it("pre-fills fields and shows the existing skill in edit mode", () => {
    render(
      <InternshipForm
        mode="edit"
        catalog={catalog}
        initial={existing()}
        submitting={false}
        error={null}
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByLabelText("Title")).toHaveValue("Backend Intern");
    expect(screen.getByLabelText("Location")).toHaveValue("Pune");
    expect(screen.getByRole("button", { name: "Save Changes" })).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("shows the error prop", () => {
    render(
      <InternshipForm
        mode="create"
        catalog={catalog}
        submitting={false}
        error="Could not create the internship. Please try again."
        onSubmit={vi.fn()}
        onCancel={vi.fn()}
      />,
    );
    expect(screen.getByText(/Could not create the internship/)).toBeInTheDocument();
  });
});
