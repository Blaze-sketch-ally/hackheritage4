import { afterEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getInstitutionEvent: vi.fn(),
  updateInstitutionEventStatus: vi.fn(),
  updateInstitutionEvent: vi.fn(),
}));

vi.mock("@/lib/institution/events", () => ({
  getInstitutionEvent: mocks.getInstitutionEvent,
  updateInstitutionEventStatus: mocks.updateInstitutionEventStatus,
  updateInstitutionEvent: mocks.updateInstitutionEvent,
  createInstitutionEvent: vi.fn(),
}));

vi.mock("@/lib/institution/departments", () => ({
  getInstitutionDepartments: vi.fn().mockResolvedValue({ departments: [] }),
}));

vi.mock("@/lib/institution/industry-partners", () => ({
  searchIndustryPartnerCompanies: vi.fn().mockResolvedValue({ companies: [] }),
}));

import { InstitutionEventDetailView } from "@/components/institution/events/event-detail-view";
import { ApiError } from "@/lib/api";
import type { EventDetail } from "@/types/institution-event";

function event(overrides: Partial<EventDetail> = {}): EventDetail {
  return {
    id: "e1",
    source: "INSTITUTION",
    title: "Placement Orientation 2026",
    event_type: "PLACEMENT_ORIENTATION",
    status: "DRAFT",
    industry_id: null,
    company_name: null,
    mode: "ONSITE",
    venue: "Main Auditorium",
    start_at: "2026-09-10T09:00:00Z",
    end_at: null,
    registration_deadline: null,
    target_department_ids: ["dept-1"],
    target_department_names: ["CSE"],
    target_batches: [2026],
    includes_faculty: false,
    platform_wide: false,
    description: "Kickoff session for final-year placements.",
    instructions: null,
    registration_note: "No registration tracking is available.",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("InstitutionEventDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches the event once on mount", () => {
    mocks.getInstitutionEvent.mockReturnValue(new Promise(() => {}));
    render(<InstitutionEventDetailView eventId="e1" />);
    expect(mocks.getInstitutionEvent).toHaveBeenCalledWith("e1");
  });

  it("shows a loading state", () => {
    mocks.getInstitutionEvent.mockReturnValue(new Promise(() => {}));
    render(<InstitutionEventDetailView eventId="e1" />);
    expect(screen.getByText(/Loading event/i)).toBeInTheDocument();
  });

  it("shows a not-visible message on 404", async () => {
    mocks.getInstitutionEvent.mockRejectedValueOnce(new ApiError(404, "not found"));
    render(<InstitutionEventDetailView eventId="e1" />);
    expect(await screen.findByText(/isn't visible to your institution/i)).toBeInTheDocument();
  });

  it("renders overview, audience and the participation note (never a fabricated count)", async () => {
    mocks.getInstitutionEvent.mockResolvedValueOnce(event());
    render(<InstitutionEventDetailView eventId="e1" />);

    expect(await screen.findByText("Placement Orientation 2026")).toBeInTheDocument();
    expect(screen.getByText("Kickoff session for final-year placements.")).toBeInTheDocument();
    expect(screen.getByText(/CSE/)).toBeInTheDocument();
    expect(screen.getByText("No registration tracking is available.")).toBeInTheDocument();
    expect(screen.queryByText(/registered/i)).not.toBeInTheDocument();
  });

  it("shows the Publish action for a DRAFT institution-owned event", async () => {
    mocks.getInstitutionEvent.mockResolvedValueOnce(event({ status: "DRAFT" }));
    render(<InstitutionEventDetailView eventId="e1" />);
    await screen.findByText("Placement Orientation 2026");
    expect(screen.getByRole("button", { name: /publish/i })).toBeInTheDocument();
  });

  it("never shows lifecycle actions for a platform-wide industry workshop", async () => {
    mocks.getInstitutionEvent.mockResolvedValueOnce(
      event({ source: "INDUSTRY_WORKSHOP", status: "PUBLISHED", platform_wide: true, company_name: "Acme Corp" }),
    );
    render(<InstitutionEventDetailView eventId="e1" />);
    await screen.findByText("Placement Orientation 2026");
    expect(screen.queryByRole("button", { name: /edit/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /publish/i })).not.toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /cancel event/i })).not.toBeInTheDocument();
  });

  it("transitions status after clicking the lifecycle action", async () => {
    mocks.getInstitutionEvent.mockResolvedValueOnce(event({ status: "DRAFT" }));
    mocks.updateInstitutionEventStatus.mockResolvedValueOnce(event({ status: "PUBLISHED" }));
    render(<InstitutionEventDetailView eventId="e1" />);
    await screen.findByText("Placement Orientation 2026");

    fireEvent.click(screen.getByRole("button", { name: /publish/i }));
    expect(mocks.updateInstitutionEventStatus).toHaveBeenCalledWith("e1", "PUBLISHED");
    expect(await screen.findByText("Published")).toBeInTheDocument();
  });
});
