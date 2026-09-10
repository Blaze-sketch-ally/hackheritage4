import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";

const mocks = vi.hoisted(() => ({
  getInstitutionEvents: vi.fn(),
  getInstitutionEventOverview: vi.fn(),
  createInstitutionEvent: vi.fn(),
}));

vi.mock("@/lib/institution/events", () => ({
  getInstitutionEvents: mocks.getInstitutionEvents,
  getInstitutionEventOverview: mocks.getInstitutionEventOverview,
  createInstitutionEvent: mocks.createInstitutionEvent,
  updateInstitutionEvent: vi.fn(),
  updateInstitutionEventStatus: vi.fn(),
}));

vi.mock("@/lib/institution/departments", () => ({
  getInstitutionDepartments: vi.fn().mockResolvedValue({ departments: [] }),
}));

vi.mock("@/lib/institution/industry-partners", () => ({
  searchIndustryPartnerCompanies: vi.fn().mockResolvedValue({ companies: [] }),
}));

import { InstitutionEventsView } from "@/components/institution/events/events-view";
import { ApiError } from "@/lib/api";
import type { EventListResponse, EventOverviewResponse, EventRow } from "@/types/institution-event";

function row(overrides: Partial<EventRow> = {}): EventRow {
  return {
    id: "e1",
    source: "INSTITUTION",
    title: "Placement Orientation 2026",
    event_type: "PLACEMENT_ORIENTATION",
    status: "PUBLISHED",
    industry_id: null,
    company_name: null,
    mode: "ONSITE",
    venue: "Main Auditorium",
    start_at: "2026-09-10T09:00:00Z",
    end_at: null,
    registration_deadline: null,
    target_department_ids: [],
    target_department_names: [],
    target_batches: [],
    includes_faculty: false,
    platform_wide: false,
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

function list(overrides: Partial<EventListResponse> = {}): EventListResponse {
  return {
    events: [row()],
    type_options: ["SEMINAR", "PLACEMENT_ORIENTATION"],
    status_options: ["DRAFT", "PUBLISHED", "ONGOING", "COMPLETED", "CANCELLED"],
    mode_options: ["ONSITE", "REMOTE", "HYBRID"],
    registration_note: "No registration tracking is available.",
    ...overrides,
  };
}

function overview(overrides: Partial<EventOverviewResponse> = {}): EventOverviewResponse {
  return {
    kpis: {
      total_events: 1,
      upcoming_events: 1,
      ongoing_events: 0,
      completed_events: 0,
      industry_events: 0,
      institution_organized_events: 1,
      platform_workshops: 0,
    },
    tenancy_note: "Tenancy note",
    registration_note: "No registration tracking is available.",
    ...overrides,
  };
}

describe("InstitutionEventsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("fetches events and overview once on mount", () => {
    mocks.getInstitutionEvents.mockReturnValue(new Promise(() => {}));
    mocks.getInstitutionEventOverview.mockReturnValue(new Promise(() => {}));
    render(<InstitutionEventsView />);
    expect(mocks.getInstitutionEvents).toHaveBeenCalledTimes(1);
    expect(mocks.getInstitutionEventOverview).toHaveBeenCalledTimes(1);
  });

  it("shows a loading state", () => {
    mocks.getInstitutionEvents.mockReturnValue(new Promise(() => {}));
    mocks.getInstitutionEventOverview.mockReturnValue(new Promise(() => {}));
    render(<InstitutionEventsView />);
    expect(screen.getByText(/Loading events/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getInstitutionEvents.mockRejectedValueOnce(new ApiError(500, "boom"));
    mocks.getInstitutionEventOverview.mockResolvedValueOnce(overview());
    render(<InstitutionEventsView />);
    expect(await screen.findByText("boom")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("renders KPIs and the event grouped into an Upcoming section", async () => {
    mocks.getInstitutionEvents.mockResolvedValueOnce(list());
    mocks.getInstitutionEventOverview.mockResolvedValueOnce(overview());
    render(<InstitutionEventsView />);

    expect(await screen.findByText("Placement Orientation 2026")).toBeInTheDocument();
    expect(screen.getByText("Total Events")).toBeInTheDocument();
    expect(screen.getByText(/Upcoming \(1\)/)).toBeInTheDocument();
  });

  it("labels a platform-wide industry workshop as industry-hosted", async () => {
    mocks.getInstitutionEvents.mockResolvedValueOnce(
      list({
        events: [
          row({
            id: "w1",
            source: "INDUSTRY_WORKSHOP",
            title: "React Bootcamp",
            event_type: "WORKSHOP",
            company_name: "Acme Corp",
            platform_wide: true,
          }),
        ],
      }),
    );
    mocks.getInstitutionEventOverview.mockResolvedValueOnce(overview());
    render(<InstitutionEventsView />);
    expect(await screen.findByText("React Bootcamp")).toBeInTheDocument();
    expect(screen.getByText("Industry-hosted")).toBeInTheDocument();
  });

  it("shows an empty state when there are no events", async () => {
    mocks.getInstitutionEvents.mockResolvedValueOnce(list({ events: [] }));
    mocks.getInstitutionEventOverview.mockResolvedValueOnce(
      overview({
        kpis: {
          total_events: 0,
          upcoming_events: 0,
          ongoing_events: 0,
          completed_events: 0,
          industry_events: 0,
          institution_organized_events: 0,
          platform_workshops: 0,
        },
      }),
    );
    render(<InstitutionEventsView />);
    expect(await screen.findByText("No events yet")).toBeInTheDocument();
  });

  it("surfaces the tenancy and registration notes, never a fabricated registration count", async () => {
    mocks.getInstitutionEvents.mockResolvedValueOnce(list());
    mocks.getInstitutionEventOverview.mockResolvedValueOnce(overview());
    render(<InstitutionEventsView />);
    expect(await screen.findByText("Tenancy note")).toBeInTheDocument();
    expect(screen.getByText("No registration tracking is available.")).toBeInTheDocument();
    expect(screen.queryByText(/registrations?:/i)).not.toBeInTheDocument();
  });
});
