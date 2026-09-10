import { describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import { MentorshipForm } from "@/components/industry/mentorship/mentorship-form";
import type { IndustryMentorship } from "@/types/industry-mentorship";

function existing(): IndustryMentorship {
  return {
    id: "mentorship-1",
    industry_id: "industry-1",
    title: "Frontend Career Mentorship",
    description: "A 3-month 1:1 mentorship.",
    location: "Remote",
    work_mode: "REMOTE",
    duration_months: 3,
    capacity: 5,
    eligibility_criteria: null,
    application_deadline: "2026-12-01T00:00:00Z",
    start_date: "2026-09-15",
    status: "DRAFT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
  };
}

function renderForm(props: Partial<React.ComponentProps<typeof MentorshipForm>> = {}) {
  return render(
    <MentorshipForm
      mode="create"
      submitting={false}
      error={null}
      onSubmit={vi.fn()}
      onCancel={vi.fn()}
      {...props}
    />,
  );
}

describe("MentorshipForm", () => {
  it("renders the section cards and a Save Draft action in create mode", () => {
    renderForm();
    expect(screen.getByText("Basic Information")).toBeInTheDocument();
    expect(screen.getByText("Mentorship Details")).toBeInTheDocument();
    expect(screen.getByText("Timeline & Eligibility")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Save Draft" })).toBeInTheDocument();
  });

  it("blocks submit and shows errors when required fields are empty", async () => {
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(screen.getByText("A title is required.")).toBeInTheDocument();
    expect(screen.getByText("A description is required.")).toBeInTheDocument();
    expect(screen.getByText("A location is required.")).toBeInTheDocument();
    expect(screen.getByText("Select a work mode.")).toBeInTheDocument();
    expect(screen.getByText("Duration is required.")).toBeInTheDocument();
    expect(screen.getByText("Capacity is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects an invalid duration", async () => {
    // Work mode is left unset here (it's a base-ui Select with no
    // established click-through test pattern in this repo) -- that also
    // triggers its own "Select a work mode." error, which is fine: this
    // test only asserts the duration error is among them.
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.type(screen.getByLabelText("Title"), "Mentorship");
    await userEvent.type(screen.getByLabelText("Description"), "Learn things.");
    await userEvent.type(screen.getByLabelText("Location"), "Remote");
    await userEvent.type(screen.getByLabelText("Duration (months)"), "48");
    await userEvent.type(screen.getByLabelText("Capacity"), "5");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(screen.getByText(/between 1 and 24/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("rejects a zero capacity", async () => {
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.type(screen.getByLabelText("Title"), "Mentorship");
    await userEvent.type(screen.getByLabelText("Description"), "Learn things.");
    await userEvent.type(screen.getByLabelText("Location"), "Remote");
    await userEvent.type(screen.getByLabelText("Duration (months)"), "3");
    await userEvent.type(screen.getByLabelText("Capacity"), "0");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(screen.getByText(/Enter a whole number of 1 or more/i)).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("submits a normalised payload from a valid edit form", async () => {
    // Edit mode starts with work_mode already prefilled from `initial`,
    // so this covers a full valid submission without needing to drive
    // the Select popup.
    const onSubmit = vi.fn();
    renderForm({ mode: "edit", initial: existing(), onSubmit });

    const title = screen.getByLabelText("Title");
    await userEvent.clear(title);
    await userEvent.type(title, "  Updated Mentorship  ");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.title).toBe("Updated Mentorship");
    expect(payload.location).toBe("Remote");
    expect(payload.work_mode).toBe("REMOTE");
    expect(payload.duration_months).toBe(3);
    expect(payload.capacity).toBe(5);
  });

  it("pre-fills fields in edit mode", () => {
    renderForm({ mode: "edit", initial: existing() });
    expect(screen.getByLabelText("Title")).toHaveValue("Frontend Career Mentorship");
    expect(screen.getByLabelText("Location")).toHaveValue("Remote");
    expect(screen.getByLabelText("Duration (months)")).toHaveValue("3");
    expect(screen.getByLabelText("Capacity")).toHaveValue("5");
    expect(screen.getByRole("button", { name: "Save Changes" })).toBeInTheDocument();
  });

  it("shows the error prop", () => {
    renderForm({ error: "Could not create the mentorship opportunity. Please try again." });
    expect(screen.getByText(/Could not create the mentorship opportunity/)).toBeInTheDocument();
  });
});
