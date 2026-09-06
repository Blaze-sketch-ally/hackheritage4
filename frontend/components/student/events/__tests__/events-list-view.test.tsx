import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listEvents: vi.fn(),
}));

vi.mock("@/lib/student/events", () => ({ listEvents: mocks.listEvents }));

import { EventsListView } from "@/components/student/events/events-list-view";
import { ApiError } from "@/lib/api";
import type { StudentEventSummary } from "@/types/student-event";

function event(overrides: Partial<StudentEventSummary> = {}): StudentEventSummary {
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
    ...overrides,
  };
}

describe("EventsListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.listEvents.mockReturnValue(new Promise(() => {}));
    render(<EventsListView />);
    expect(screen.getByLabelText("Loading events")).toBeInTheDocument();
  });

  it("renders real event cards with title and organizer", async () => {
    mocks.listEvents.mockResolvedValueOnce({
      events: [event(), event({ id: "e-2", title: "GraphQL Deep Dive" })],
    });
    render(<EventsListView />);

    expect(await screen.findByText("Intro to Kubernetes")).toBeInTheDocument();
    expect(screen.getByText("GraphQL Deep Dive")).toBeInTheDocument();
    expect(screen.getAllByText("Acme")).toHaveLength(2);
  });

  it("shows the honest empty state when there are no events", async () => {
    mocks.listEvents.mockResolvedValueOnce({ events: [] });
    render(<EventsListView />);
    expect(await screen.findByText("No upcoming events.")).toBeInTheDocument();
  });

  it("does not render any card when the API returns nothing", async () => {
    mocks.listEvents.mockResolvedValueOnce({ events: [] });
    const { container } = render(<EventsListView />);
    await screen.findByText("No upcoming events.");
    expect(container.querySelector("a[href^='/student/events/']")).toBeNull();
  });

  it("shows an error state with retry", async () => {
    mocks.listEvents.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<EventsListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("re-fetches with the selected work mode filter", async () => {
    mocks.listEvents.mockResolvedValue({ events: [event()] });
    render(<EventsListView />);
    await screen.findByText("Intro to Kubernetes");
    expect(mocks.listEvents).toHaveBeenLastCalledWith(undefined);

    await userEvent.click(screen.getByRole("button", { name: "Online" }));
    expect(mocks.listEvents).toHaveBeenLastCalledWith({ workMode: "REMOTE" });
  });

  it("filters the rendered list by title search", async () => {
    mocks.listEvents.mockResolvedValueOnce({
      events: [event(), event({ id: "e-2", title: "Data Pipelines 101" })],
    });
    render(<EventsListView />);
    await screen.findByText("Intro to Kubernetes");

    await userEvent.type(screen.getByLabelText("Search events"), "data");

    expect(screen.queryByText("Intro to Kubernetes")).not.toBeInTheDocument();
    expect(screen.getByText("Data Pipelines 101")).toBeInTheDocument();
  });

  it("links each card to its detail route", async () => {
    mocks.listEvents.mockResolvedValueOnce({ events: [event()] });
    const { container } = render(<EventsListView />);
    await screen.findByText("Intro to Kubernetes");
    expect(
      container.querySelector('a[href="/student/events/11111111-1111-1111-1111-111111111111"]'),
    ).not.toBeNull();
  });
});
