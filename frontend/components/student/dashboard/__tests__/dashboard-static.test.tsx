import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getRecommendations: vi.fn(),
  listEvents: vi.fn(),
}));

vi.mock("@/lib/student/recommendations", () => ({ getRecommendations: mocks.getRecommendations }));
vi.mock("@/lib/student/events", () => ({ listEvents: mocks.listEvents }));

import { DashboardRecommendations } from "@/components/student/dashboard/dashboard-recommendations";
import { DashboardAnnouncements } from "@/components/student/dashboard/dashboard-announcements";
import { DashboardAiSuggestions } from "@/components/student/dashboard/dashboard-ai-suggestions";
import { ApiError } from "@/lib/api";

// Strings that appeared in the deleted S1 mock data — none may ever resurface.
const FORMER_MOCK_CONTENT = [
  "Nimbus Systems",
  "Verdant Labs",
  "% match",
  "Improve Docker Skills",
  "Complete AWS Essentials",
  "Data Structures Skill Assessment",
  "Resume Building Workshop",
  "Campus Internship Drive",
];

function recResponse(over: Partial<Parameters<typeof mocks.getRecommendations.mockResolvedValue>[0]> = {}) {
  return {
    mode: "PERSONAL" as const,
    target_role: null,
    opportunities: [],
    learning: [],
    ...over,
  };
}

const OPP = {
  type: "INTERNSHIP" as const,
  id: "internship_1",
  title: "Backend Intern",
  description: "d",
  company: "Acme",
  location: "Pune",
  work_mode: "HYBRID",
  detail_path: "/student/internships/internship_1",
  match_score: 70,
  match_band: "GOOD" as const,
  matched_skill_count: 3,
  required_skill_count: 5,
  relevant_skills: ["Python"],
};

const EVENT = {
  id: "ev-1",
  title: "Intro to Kubernetes",
  description: "d",
  location: "Bengaluru",
  work_mode: "ONSITE" as const,
  start_date: "2026-10-01",
  application_deadline: null,
  duration_days: 1,
  organizer: { id: "i-1", company_name: "Acme", industry_sector: null, logo_url: null },
  created_at: "2026-09-01T00:00:00Z",
};

describe("DashboardRecommendations (real S7 preview)", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state, then real recommended opportunities with a truthful skill count", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(recResponse({ opportunities: [OPP] }));
    const { container } = render(<DashboardRecommendations />);

    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
    expect(screen.getByText(/Matches 3 of 5 skills/i)).toBeInTheDocument();
    expect(container.querySelector('a[href="/student/recommendations"]')).not.toBeNull();
    expect(container.querySelector('a[href="/student/internships/internship_1"]')).not.toBeNull();
    // no fabricated percentage, no resurrected mock content
    expect(container.textContent).not.toMatch(/\d+%\s*match/i);
    for (const s of FORMER_MOCK_CONTENT) expect(screen.queryByText(s)).not.toBeInTheDocument();
  });

  it("shows an honest empty state when the API returns no recommendations", async () => {
    mocks.getRecommendations.mockResolvedValueOnce(recResponse());
    render(<DashboardRecommendations />);
    expect(await screen.findByText("No recommendations yet")).toBeInTheDocument();
  });

  it("degrades to a retryable error, never a stuck skeleton", async () => {
    mocks.getRecommendations
      .mockRejectedValueOnce(new ApiError(500, "down"))
      .mockResolvedValueOnce(recResponse({ opportunities: [OPP] }));
    render(<DashboardRecommendations />);
    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Backend Intern")).toBeInTheDocument();
  });
});

describe("DashboardAnnouncements (real S4 events preview)", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders real upcoming events from the canonical adapter", async () => {
    mocks.listEvents.mockResolvedValueOnce({ events: [EVENT] });
    const { container } = render(<DashboardAnnouncements />);
    expect(await screen.findByText("Intro to Kubernetes")).toBeInTheDocument();
    expect(container.querySelector('a[href="/student/events/ev-1"]')).not.toBeNull();
    for (const s of FORMER_MOCK_CONTENT) expect(screen.queryByText(s)).not.toBeInTheDocument();
  });

  it("shows a truthful empty state when there are no events", async () => {
    mocks.listEvents.mockResolvedValueOnce({ events: [] });
    render(<DashboardAnnouncements />);
    expect(await screen.findByText("Nothing scheduled")).toBeInTheDocument();
  });

  it("degrades to a retryable error state", async () => {
    mocks.listEvents.mockRejectedValueOnce(new ApiError(500, "down"));
    render(<DashboardAnnouncements />);
    expect(await screen.findByText(/couldn.t load upcoming events/i)).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });
});

describe("DashboardAiSuggestions", () => {
  it("stays an honest coming-soon state pointing at the real Skill Gap analysis", () => {
    const { container } = render(<DashboardAiSuggestions />);
    expect(screen.getByText(/coming soon/i)).toBeInTheDocument();
    expect(container.querySelector('a[href="/student/skill-gap"]')).not.toBeNull();
    for (const s of FORMER_MOCK_CONTENT) expect(screen.queryByText(s)).not.toBeInTheDocument();
  });
});
