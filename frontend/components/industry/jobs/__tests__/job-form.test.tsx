import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { JobForm } from "@/components/industry/jobs/job-form";
import type { CatalogSkill } from "@/lib/industry/skills";
import type { Job } from "@/types/job";

const catalog: CatalogSkill[] = [
  { id: "s1", name: "Python", category_name: "Programming", description: null },
  { id: "s2", name: "SQL", category_name: "Data", description: null },
];

function existing(): Job {
  return {
    id: "job-1",
    industry_id: "industry-1",
    title: "Backend Engineer",
    description: "Own our API platform.",
    location: "Pune",
    work_mode: "HYBRID",
    employment_type: "FULL_TIME",
    salary_min: 1800000,
    salary_max: 2600000,
    salary_currency: "INR",
    experience_min_years: 2,
    openings: 3,
    eligibility_criteria: null,
    application_deadline: "2026-12-01",
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

function renderForm(props: Partial<React.ComponentProps<typeof JobForm>> = {}) {
  return render(
    <JobForm
      mode="create"
      catalog={catalog}
      submitting={false}
      error={null}
      onSubmit={vi.fn()}
      onCancel={vi.fn()}
      {...props}
    />,
  );
}

describe("JobForm", () => {
  it("renders the section cards and a Save Draft action in create mode", () => {
    renderForm();
    expect(screen.getByText("Basic Information")).toBeInTheDocument();
    expect(screen.getByText("Job Details")).toBeInTheDocument();
    expect(screen.getByText("Compensation")).toBeInTheDocument();
    expect(screen.getByText("Recruitment")).toBeInTheDocument();
    expect(screen.getByText("Required Skills")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Draft" })).toBeInTheDocument();
  });

  it("blocks submit and shows errors when title/description are empty", async () => {
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(screen.getByText("A title is required.")).toBeInTheDocument();
    expect(screen.getByText("A description is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects an inverted salary range", async () => {
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.type(screen.getByLabelText("Title"), "Backend Engineer");
    await userEvent.type(screen.getByLabelText("Description"), "Own the platform.");
    await userEvent.type(screen.getByLabelText("Salary (min)"), "200000");
    await userEvent.type(screen.getByLabelText("Salary (max)"), "100000");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(screen.getByText(/can't be lower than the minimum/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a normalised payload from a valid create form", async () => {
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.type(screen.getByLabelText("Title"), "  Backend Engineer  ");
    await userEvent.type(screen.getByLabelText("Description"), "Own the platform.");
    await userEvent.type(screen.getByLabelText("Minimum Experience (years)"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.title).toBe("Backend Engineer");
    expect(payload.experience_min_years).toBe(2);
    expect(payload.location).toBeNull();
    expect(payload.skills).toEqual([]);
  });

  it("pre-fills fields and shows the existing skill in edit mode", () => {
    renderForm({ mode: "edit", initial: existing() });
    expect(screen.getByLabelText("Title")).toHaveValue("Backend Engineer");
    expect(screen.getByLabelText("Location")).toHaveValue("Pune");
    expect(screen.getByLabelText("Salary (min)")).toHaveValue("1800000");
    expect(screen.getByRole("button", { name: "Save Changes" })).toBeInTheDocument();
    expect(screen.getByText("Python")).toBeInTheDocument();
  });

  it("shows the error prop", () => {
    renderForm({ error: "Could not create the job. Please try again." });
    expect(screen.getByText(/Could not create the job/)).toBeInTheDocument();
  });
});
