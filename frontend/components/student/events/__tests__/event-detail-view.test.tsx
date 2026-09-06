import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getEvent: vi.fn(),
}));

vi.mock("@/lib/student/events", () => ({ getEvent: mocks.getEvent }));

import { EventDetailView } from "@/components/student/events/event-detail-view";
import { ApiError } from "@/lib/api";
import type { StudentEventDetail } from "@/types/student-event";

function detail(overrides: Partial<StudentEventDetail> = {}): StudentEventDetail {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    title: "Intro to Kubernetes",
    description: "A hands-on afternoon workshop.",
    location: "Bengaluru",
    work_mode: "ONSITE",
    start_date: "2026-10-01",
    application_deadline: "2026-09-20",
    duration_days: 1,
    organizer: { id: "i-1", company_name: "Acme", industry_sector: "Software", logo_url: null },
    created_at: "2026-09-01T00:00:00Z",
    capacity: 30,
    eligibility_criteria: "Open to all students.",
    registration_available: false,
    ...overrides,
  };
}

describe("EventDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getEvent.mockReturnValue(new Promise(() => {}));
    render(<EventDetailView eventId="e-1" />);
    expect(screen.getByLabelText("Loading event")).toBeInTheDocument();
  });

  it("renders the real event details", async () => {
    mocks.getEvent.mockResolvedValueOnce(detail());
    render(<EventDetailView eventId="e-1" />);

    expect(await screen.findByText("Intro to Kubernetes")).toBeInTheDocument();
    expect(screen.getByText(/Acme/)).toBeInTheDocument();
    expect(screen.getByText("A hands-on afternoon workshop.")).toBeInTheDocument();
    expect(screen.getByText("Open to all students.")).toBeInTheDocument();
  });

  it("shows an honest 'registration not available yet' state and no register button", async () => {
    mocks.getEvent.mockResolvedValueOnce(detail());
    render(<EventDetailView eventId="e-1" />);
    await screen.findByText("Intro to Kubernetes");

    expect(screen.getByText(/registration for events isn.t available yet/i)).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /register/i })).not.toBeInTheDocument();
  });

  it("shows a not-found state (no retry) on a 404", async () => {
    mocks.getEvent.mockRejectedValueOnce(new ApiError(404, "This event is not available."));
    render(<EventDetailView eventId="missing" />);
    expect(await screen.findByText("This event is not available.")).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /try again/i })).not.toBeInTheDocument();
  });

  it("shows an error state with retry on a server error, then recovers", async () => {
    mocks.getEvent
      .mockRejectedValueOnce(new ApiError(500, "Server is down."))
      .mockResolvedValueOnce(detail());
    render(<EventDetailView eventId="e-1" />);

    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Intro to Kubernetes")).toBeInTheDocument();
  });

  it("does not fabricate an attendee or registration count", async () => {
    mocks.getEvent.mockResolvedValueOnce(detail());
    const { container } = render(<EventDetailView eventId="e-1" />);
    await screen.findByText("Intro to Kubernetes");
    expect(container.textContent).not.toMatch(/\d+\s*(registered|attendees|going|spots taken)/i);
  });
});
