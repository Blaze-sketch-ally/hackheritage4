import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { ProjectForm } from "@/components/industry/projects/project-form";
import type { IndustryProject } from "@/types/industry-project";

function existing(): IndustryProject {
  return {
    id: "project-1",
    industry_id: "industry-1",
    title: "Campus Recommendation Engine",
    description: "Build a recommender.",
    location: "Remote",
    work_mode: "REMOTE",
    duration_months: 3,
    team_size: 4,
    eligibility_criteria: null,
    application_deadline: "2026-12-01",
    start_date: "2026-09-15",
    status: "DRAFT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
  };
}

function renderForm(props: Partial<React.ComponentProps<typeof ProjectForm>> = {}) {
  return render(
    <ProjectForm
      mode="create"
      submitting={false}
      error={null}
      onSubmit={vi.fn()}
      onCancel={vi.fn()}
      {...props}
    />,
  );
}

describe("ProjectForm", () => {
  it("renders the section cards and a Save Draft action in create mode", () => {
    renderForm();
    expect(screen.getByText("Basic Information")).toBeInTheDocument();
    expect(screen.getByText("Project Details")).toBeInTheDocument();
    expect(screen.getByText("Timeline & Eligibility")).toBeInTheDocument();
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

  it("rejects an invalid duration", async () => {
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.type(screen.getByLabelText("Title"), "Recommender");
    await userEvent.type(screen.getByLabelText("Description"), "Build it.");
    await userEvent.type(screen.getByLabelText("Duration (months)"), "48");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(screen.getByText(/between 1 and 24/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a normalised payload from a valid create form", async () => {
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.type(screen.getByLabelText("Title"), "  Recommender  ");
    await userEvent.type(screen.getByLabelText("Description"), "Build it.");
    await userEvent.type(screen.getByLabelText("Team Size"), "4");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.title).toBe("Recommender");
    expect(payload.team_size).toBe(4);
    expect(payload.location).toBeNull();
  });

  it("pre-fills fields in edit mode", () => {
    renderForm({ mode: "edit", initial: existing() });
    expect(screen.getByLabelText("Title")).toHaveValue("Campus Recommendation Engine");
    expect(screen.getByLabelText("Location")).toHaveValue("Remote");
    expect(screen.getByLabelText("Team Size")).toHaveValue("4");
    expect(screen.getByRole("button", { name: "Save Changes" })).toBeInTheDocument();
  });

  it("shows the error prop", () => {
    renderForm({ error: "Could not create the project. Please try again." });
    expect(screen.getByText(/Could not create the project/)).toBeInTheDocument();
  });
});
