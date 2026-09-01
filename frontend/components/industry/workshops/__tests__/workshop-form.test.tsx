import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { WorkshopForm } from "@/components/industry/workshops/workshop-form";
import type { IndustryWorkshop } from "@/types/industry-workshop";

function existing(): IndustryWorkshop {
  return {
    id: "workshop-1",
    industry_id: "industry-1",
    title: "Intro to Git Workshop",
    description: "A hands-on session.",
    location: "Remote",
    work_mode: "REMOTE",
    duration_days: 1,
    capacity: 50,
    eligibility_criteria: null,
    application_deadline: "2026-12-01",
    start_date: "2026-09-15",
    status: "DRAFT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
  };
}

function renderForm(props: Partial<React.ComponentProps<typeof WorkshopForm>> = {}) {
  return render(
    <WorkshopForm
      mode="create"
      submitting={false}
      error={null}
      onSubmit={vi.fn()}
      onCancel={vi.fn()}
      {...props}
    />,
  );
}

describe("WorkshopForm", () => {
  it("renders the section cards and a Save Draft action in create mode", () => {
    renderForm();
    expect(screen.getByText("Basic Information")).toBeInTheDocument();
    expect(screen.getByText("Workshop Details")).toBeInTheDocument();
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

    await userEvent.type(screen.getByLabelText("Title"), "Workshop");
    await userEvent.type(screen.getByLabelText("Description"), "Learn things.");
    await userEvent.type(screen.getByLabelText("Duration (days)"), "400");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(screen.getByText(/between 1 and 365/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects a zero capacity", async () => {
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.type(screen.getByLabelText("Title"), "Workshop");
    await userEvent.type(screen.getByLabelText("Description"), "Learn things.");
    await userEvent.type(screen.getByLabelText("Capacity"), "0");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(screen.getByText(/Enter a whole number of 1 or more/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a normalised payload from a valid create form", async () => {
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.type(screen.getByLabelText("Title"), "  Workshop  ");
    await userEvent.type(screen.getByLabelText("Description"), "Learn things.");
    await userEvent.type(screen.getByLabelText("Duration (days)"), "2");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.title).toBe("Workshop");
    expect(payload.duration_days).toBe(2);
    expect(payload.location).toBeNull();
  });

  it("pre-fills fields in edit mode", () => {
    renderForm({ mode: "edit", initial: existing() });
    expect(screen.getByLabelText("Title")).toHaveValue("Intro to Git Workshop");
    expect(screen.getByLabelText("Location")).toHaveValue("Remote");
    expect(screen.getByLabelText("Duration (days)")).toHaveValue("1");
    expect(screen.getByRole("button", { name: "Save Changes" })).toBeInTheDocument();
  });

  it("shows the error prop", () => {
    renderForm({ error: "Could not create the workshop. Please try again." });
    expect(screen.getByText(/Could not create the workshop/)).toBeInTheDocument();
  });
});
