import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

import {
  FacultyOpportunityManagementView,
  type FacultyOpportunityManagementApi,
} from "@/components/shared/faculty-opportunity-management-view";
import { ApiError } from "@/lib/api";

function opportunity(overrides = {}) {
  return {
    id: "opp-1",
    owner_id: "owner-1",
    title: "Data Science Research Collaboration",
    description: "Collaborate on a joint dataset.",
    location: "Remote",
    work_mode: "REMOTE",
    capacity: 2,
    eligibility_criteria: null,
    application_deadline: null,
    start_date: null,
    status: "DRAFT",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function eoi(overrides = {}) {
  return {
    id: "eoi-1",
    source: "INDUSTRY",
    opportunity_id: "opp-1",
    opportunity_title: "Data Science Research Collaboration",
    faculty_id: "faculty-1",
    status: "SUBMITTED",
    message: "Interested!",
    reviewed_by: null,
    reviewer_note: null,
    created_at: "2026-01-02T00:00:00Z",
    updated_at: "2026-01-02T00:00:00Z",
    engagement: null,
    ...overrides,
  };
}

function engagement(overrides = {}) {
  return {
    id: "eng-1",
    source_kind: "INDUSTRY_EOI",
    industry_eoi_id: "eoi-1",
    institution_eoi_id: null,
    faculty_id: "faculty-1",
    organization_id: "owner-1",
    status: "PLANNED",
    start_date: null,
    end_date: null,
    notes: null,
    created_at: "2026-01-03T00:00:00Z",
    updated_at: "2026-01-03T00:00:00Z",
    ...overrides,
  };
}

function makeApi(overrides: Partial<FacultyOpportunityManagementApi> = {}): FacultyOpportunityManagementApi {
  return {
    listOpportunities: vi.fn().mockResolvedValue({ opportunities: [] }),
    createOpportunity: vi.fn(),
    updateOpportunity: vi.fn(),
    publishOpportunity: vi.fn(),
    closeOpportunity: vi.fn(),
    listEois: vi.fn().mockResolvedValue({ expressions: [] }),
    reviewEoi: vi.fn(),
    updateEngagementStatus: vi.fn(),
    ...overrides,
  };
}

describe("FacultyOpportunityManagementView", () => {
  afterEach(() => {
    vi.clearAllMocks();
  });

  it("lists the owner's own opportunities with status and lifecycle actions", async () => {
    const api = makeApi({ listOpportunities: vi.fn().mockResolvedValue({ opportunities: [opportunity()] }) });
    render(<FacultyOpportunityManagementView api={api} />);

    expect(await screen.findByText("Data Science Research Collaboration")).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Publish" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Edit" })).toBeInTheDocument();
  });

  it("creates a new opportunity via the dialog", async () => {
    const createOpportunity = vi.fn().mockResolvedValue(opportunity());
    const api = makeApi({ createOpportunity });
    render(<FacultyOpportunityManagementView api={api} />);
    await waitFor(() => expect(api.listOpportunities).toHaveBeenCalled());

    await userEvent.click(screen.getByRole("button", { name: /new faculty opportunity/i }));
    await userEvent.type(screen.getByLabelText("Title"), "New Opportunity");
    await userEvent.type(screen.getByLabelText("Description"), "A description.");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() =>
      expect(createOpportunity).toHaveBeenCalledWith(
        expect.objectContaining({ title: "New Opportunity", description: "A description." }),
      ),
    );
  });

  it("publishes a draft opportunity", async () => {
    const publishOpportunity = vi.fn().mockResolvedValue(opportunity({ status: "PUBLISHED" }));
    const api = makeApi({
      listOpportunities: vi.fn().mockResolvedValue({ opportunities: [opportunity()] }),
      publishOpportunity,
    });
    render(<FacultyOpportunityManagementView api={api} />);
    await screen.findByText("Data Science Research Collaboration");

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(publishOpportunity).toHaveBeenCalledWith("opp-1"));
  });

  it("closes a published opportunity", async () => {
    const closeOpportunity = vi.fn().mockResolvedValue(opportunity({ status: "CLOSED" }));
    const api = makeApi({
      listOpportunities: vi.fn().mockResolvedValue({ opportunities: [opportunity({ status: "PUBLISHED" })] }),
      closeOpportunity,
    });
    render(<FacultyOpportunityManagementView api={api} />);
    await screen.findByText("Data Science Research Collaboration");

    await userEvent.click(screen.getByRole("button", { name: "Close" }));

    await waitFor(() => expect(closeOpportunity).toHaveBeenCalledWith("opp-1"));
  });

  it("does not show edit/publish for a published opportunity", async () => {
    const api = makeApi({
      listOpportunities: vi.fn().mockResolvedValue({ opportunities: [opportunity({ status: "PUBLISHED" })] }),
    });
    render(<FacultyOpportunityManagementView api={api} />);
    await screen.findByText("Data Science Research Collaboration");

    expect(screen.queryByRole("button", { name: "Edit" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Publish" })).not.toBeInTheDocument();
  });

  it("shows a retryable error state on load failure", async () => {
    const listOpportunities = vi
      .fn()
      .mockRejectedValueOnce(new ApiError(500, "Could not load your Faculty opportunities."))
      .mockResolvedValueOnce({ opportunities: [opportunity()] });
    const api = makeApi({ listOpportunities });
    render(<FacultyOpportunityManagementView api={api} />);

    expect(await screen.findByText("Could not load your Faculty opportunities.")).toBeInTheDocument();
    await userEvent.click(screen.getByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Data Science Research Collaboration")).toBeInTheDocument();
  });

  it("shows expressions of interest and moves a SUBMITTED one to review", async () => {
    const reviewEoi = vi.fn().mockResolvedValue(eoi({ status: "UNDER_REVIEW" }));
    const api = makeApi({
      listEois: vi.fn().mockResolvedValue({ expressions: [eoi()] }),
      reviewEoi,
    });
    render(<FacultyOpportunityManagementView api={api} />);

    await userEvent.click(screen.getByRole("tab", { name: /expressions of interest/i }));
    expect(await screen.findByText("Data Science Research Collaboration")).toBeInTheDocument();
    expect(screen.getByText(/interested!/i)).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /move to review/i }));
    await waitFor(() => expect(reviewEoi).toHaveBeenCalledWith("eoi-1", "UNDER_REVIEW"));
  });

  it("accepts and rejects an UNDER_REVIEW expression of interest", async () => {
    const reviewEoi = vi.fn().mockResolvedValue(eoi({ status: "ACCEPTED" }));
    const api = makeApi({
      listEois: vi.fn().mockResolvedValue({ expressions: [eoi({ status: "UNDER_REVIEW" })] }),
      reviewEoi,
    });
    render(<FacultyOpportunityManagementView api={api} />);

    await userEvent.click(screen.getByRole("tab", { name: /expressions of interest/i }));
    await screen.findByText("Data Science Research Collaboration");

    expect(screen.getByRole("button", { name: /accept/i })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /reject/i })).toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: /accept/i }));
    await waitFor(() => expect(reviewEoi).toHaveBeenCalledWith("eoi-1", "ACCEPTED"));
  });

  it("does not show review actions for a terminal-state expression of interest", async () => {
    const api = makeApi({
      listEois: vi.fn().mockResolvedValue({ expressions: [eoi({ status: "ACCEPTED" })] }),
    });
    render(<FacultyOpportunityManagementView api={api} />);

    await userEvent.click(screen.getByRole("tab", { name: /expressions of interest/i }));
    await screen.findByText("Data Science Research Collaboration");

    expect(screen.queryByRole("button", { name: /accept/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /reject/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /move to review/i })).not.toBeInTheDocument();
  });

  it("labels the accept action as creating the engagement (Phase F4.1)", async () => {
    const api = makeApi({
      listEois: vi.fn().mockResolvedValue({ expressions: [eoi({ status: "UNDER_REVIEW" })] }),
    });
    render(<FacultyOpportunityManagementView api={api} />);

    await userEvent.click(screen.getByRole("tab", { name: /expressions of interest/i }));
    await screen.findByText("Data Science Research Collaboration");

    expect(screen.getByRole("button", { name: /accept & create engagement/i })).toBeInTheDocument();
  });

  it("shows the resulting engagement's status and no lifecycle actions for a PLANNED engagement it cannot yet act on", async () => {
    const api = makeApi({
      listEois: vi.fn().mockResolvedValue({
        expressions: [eoi({ status: "ACCEPTED", engagement: engagement({ status: "COMPLETED" }) })],
      }),
    });
    render(<FacultyOpportunityManagementView api={api} />);

    await userEvent.click(screen.getByRole("tab", { name: /expressions of interest/i }));
    await screen.findByText("Data Science Research Collaboration");

    expect(screen.getByText(/engagement:/i)).toBeInTheDocument();
    expect(screen.getByText("Completed")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Activate" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Complete" })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Cancel" })).not.toBeInTheDocument();
  });

  it("shows Activate/Cancel for a PLANNED engagement and activates it", async () => {
    const updateEngagementStatus = vi.fn().mockResolvedValue(engagement({ status: "ACTIVE" }));
    const api = makeApi({
      listEois: vi.fn().mockResolvedValue({
        expressions: [eoi({ status: "ACCEPTED", engagement: engagement({ status: "PLANNED" }) })],
      }),
      updateEngagementStatus,
    });
    render(<FacultyOpportunityManagementView api={api} />);

    await userEvent.click(screen.getByRole("tab", { name: /expressions of interest/i }));
    await screen.findByText("Data Science Research Collaboration");

    expect(screen.getByText(/engagement:/i)).toBeInTheDocument();
    expect(screen.getByText("Planned")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Activate" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Complete" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Activate" }));
    await waitFor(() => expect(updateEngagementStatus).toHaveBeenCalledWith("eng-1", "ACTIVE"));
  });

  it("shows Complete/Cancel for an ACTIVE engagement and completes it", async () => {
    const updateEngagementStatus = vi.fn().mockResolvedValue(engagement({ status: "COMPLETED" }));
    const api = makeApi({
      listEois: vi.fn().mockResolvedValue({
        expressions: [eoi({ status: "ACCEPTED", engagement: engagement({ status: "ACTIVE" }) })],
      }),
      updateEngagementStatus,
    });
    render(<FacultyOpportunityManagementView api={api} />);

    await userEvent.click(screen.getByRole("tab", { name: /expressions of interest/i }));
    await screen.findByText("Data Science Research Collaboration");

    expect(screen.getByText(/engagement:/i)).toBeInTheDocument();
    expect(screen.getByText("Active")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Complete" })).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Cancel" })).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: "Activate" })).not.toBeInTheDocument();

    await userEvent.click(screen.getByRole("button", { name: "Complete" }));
    await waitFor(() => expect(updateEngagementStatus).toHaveBeenCalledWith("eng-1", "COMPLETED"));
  });

  it("cancels a PLANNED engagement", async () => {
    const updateEngagementStatus = vi.fn().mockResolvedValue(engagement({ status: "CANCELLED" }));
    const api = makeApi({
      listEois: vi.fn().mockResolvedValue({
        expressions: [eoi({ status: "ACCEPTED", engagement: engagement({ status: "PLANNED" }) })],
      }),
      updateEngagementStatus,
    });
    render(<FacultyOpportunityManagementView api={api} />);

    await userEvent.click(screen.getByRole("tab", { name: /expressions of interest/i }));
    await screen.findByText("Data Science Research Collaboration");

    await userEvent.click(screen.getByRole("button", { name: "Cancel" }));
    await waitFor(() => expect(updateEngagementStatus).toHaveBeenCalledWith("eng-1", "CANCELLED"));
  });

  it("shows no engagement block for an EOI with no engagement yet", async () => {
    const api = makeApi({
      listEois: vi.fn().mockResolvedValue({ expressions: [eoi({ status: "UNDER_REVIEW" })] }),
    });
    render(<FacultyOpportunityManagementView api={api} />);

    await userEvent.click(screen.getByRole("tab", { name: /expressions of interest/i }));
    await screen.findByText("Data Science Research Collaboration");

    expect(screen.queryByText(/engagement:/i)).not.toBeInTheDocument();
  });
});
