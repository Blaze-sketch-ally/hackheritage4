import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  resolveRecipient: vi.fn(),
}));

vi.mock("@/lib/industry/collaborations", () => ({
  resolveRecipient: mocks.resolveRecipient,
}));

import { CollaborationForm } from "@/components/industry/collaborations/collaboration-form";
import { ApiError } from "@/lib/api";
import type { IndustryCollaboration } from "@/types/industry-collaboration";

function existing(): IndustryCollaboration {
  return {
    id: "collab-1",
    industry_id: "industry-1",
    recipient_id: "faculty-1",
    recipient_type: "FACULTY",
    title: "Joint Research Proposal",
    description: "A proposed research collaboration.",
    status: "DRAFT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
  };
}

function renderForm(props: Partial<React.ComponentProps<typeof CollaborationForm>> = {}) {
  return render(
    <CollaborationForm
      mode="create"
      submitting={false}
      error={null}
      onSubmit={vi.fn()}
      onCancel={vi.fn()}
      {...props}
    />,
  );
}

describe("CollaborationForm", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders the recipient section only in create mode", () => {
    renderForm({ mode: "create" });
    expect(screen.getByText("Recipient")).toBeInTheDocument();
    expect(screen.getByLabelText(/Faculty or Institution username/i)).toBeInTheDocument();
  });

  it("does not render the recipient section in edit mode", () => {
    renderForm({ mode: "edit", initial: existing() });
    expect(screen.queryByText("Recipient")).not.toBeInTheDocument();
    expect(screen.queryByLabelText(/Faculty or Institution username/i)).not.toBeInTheDocument();
  });

  it("blocks submit and shows errors when title/description are empty", async () => {
    const onSubmit = vi.fn();
    renderForm({ mode: "edit", initial: existing(), onSubmit });
    // clear prefilled fields
    await userEvent.clear(screen.getByLabelText("Title"));
    await userEvent.clear(screen.getByLabelText("Description"));

    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(screen.getByText("A title is required.")).toBeInTheDocument();
    expect(screen.getByText("A description is required.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("blocks submit in create mode until a recipient is resolved", async () => {
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.type(screen.getByLabelText("Title"), "Proposal");
    await userEvent.type(screen.getByLabelText("Description"), "Details.");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(screen.getByText("Look up and select a recipient before saving.")).toBeInTheDocument();
    expect(onSubmit).not.toHaveBeenCalled();
  });

  it("resolves a recipient and submits with the resolved id", async () => {
    mocks.resolveRecipient.mockResolvedValueOnce({
      id: "faculty-42",
      role: "FACULTY",
      full_name: "Dr. Rao",
    });
    const onSubmit = vi.fn();
    renderForm({ onSubmit });

    await userEvent.type(screen.getByLabelText(/Faculty or Institution username/i), "drrao");
    await userEvent.click(screen.getByRole("button", { name: "Find" }));

    expect(await screen.findByText("Dr. Rao")).toBeInTheDocument();
    expect(screen.getByText("Faculty")).toBeInTheDocument();

    await userEvent.type(screen.getByLabelText("Title"), "Proposal");
    await userEvent.type(screen.getByLabelText("Description"), "Details.");
    await userEvent.click(screen.getByRole("button", { name: "Save Draft" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    const payload = onSubmit.mock.calls[0][0];
    expect(payload.recipient_id).toBe("faculty-42");
    expect(payload.title).toBe("Proposal");
  });

  it("shows a not-found message when the recipient cannot be resolved", async () => {
    mocks.resolveRecipient.mockRejectedValueOnce(new ApiError(404, "not found"));
    renderForm();

    await userEvent.type(screen.getByLabelText(/Faculty or Institution username/i), "nobody");
    await userEvent.click(screen.getByRole("button", { name: "Find" }));

    expect(
      await screen.findByText("No Faculty or Institution account found with that username."),
    ).toBeInTheDocument();
  });

  it("pre-fills fields in edit mode and submits without needing a recipient lookup", async () => {
    const onSubmit = vi.fn();
    renderForm({ mode: "edit", initial: existing(), onSubmit });

    expect(screen.getByLabelText("Title")).toHaveValue("Joint Research Proposal");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    expect(onSubmit).toHaveBeenCalledTimes(1);
    expect(onSubmit.mock.calls[0][0].recipient_id).toBe("faculty-1");
  });

  it("shows the error prop", () => {
    renderForm({ error: "Could not create the collaboration. Please try again." });
    expect(screen.getByText(/Could not create the collaboration/)).toBeInTheDocument();
  });
});
