import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listLearningResources: vi.fn(),
  listMyLearningProgress: vi.fn(),
}));

vi.mock("@/lib/student/learning", () => ({
  listLearningResources: mocks.listLearningResources,
  listMyLearningProgress: mocks.listMyLearningProgress,
}));

import { LearningBrowseView } from "@/components/student/learning/learning-browse-view";
import {
  EMPTY_LEARNING_FILTERS,
  learningFiltersActive,
} from "@/components/student/learning/learning-resource-filters";
import { ApiError } from "@/lib/api";
import type { LearningResource, StudentLearningResource } from "@/types/student-learning";

function resource(overrides: Partial<LearningResource> = {}): LearningResource {
  return {
    id: "res-1",
    title: "Python for Everybody",
    description: "A gentle intro to Python.",
    url: "https://www.py4e.com/",
    provider: "py4e",
    resource_type: "COURSE",
    difficulty: "Beginner",
    estimated_minutes: 1200,
    skills: [{ skill_id: "s1", skill_name: "Python", target_level: "Beginner" }],
    progress: null,
    ...overrides,
  };
}

function progressRow(overrides: Partial<StudentLearningResource> = {}): StudentLearningResource {
  return {
    resource_id: "res-1",
    status: "SAVED",
    started_at: null,
    completed_at: null,
    created_at: "2026-09-02T00:00:00Z",
    updated_at: "2026-09-02T00:00:00Z",
    resource: null,
    ...overrides,
  };
}

function ready(resources: LearningResource[], progress: StudentLearningResource[] = []) {
  mocks.listLearningResources.mockResolvedValue({ resources });
  mocks.listMyLearningProgress.mockResolvedValue({ progress });
}

describe("LearningBrowseView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.listLearningResources.mockReturnValue(new Promise(() => {}));
    mocks.listMyLearningProgress.mockReturnValue(new Promise(() => {}));
    render(<LearningBrowseView />);
    expect(screen.getByLabelText("Loading learning resources")).toBeInTheDocument();
  });

  it("renders resources returned by the API (no mock data)", async () => {
    ready([
      resource(),
      resource({ id: "res-2", title: "SQL Basics", provider: "SQLBolt" }),
    ]);
    render(<LearningBrowseView />);
    expect(await screen.findByText("Python for Everybody")).toBeInTheDocument();
    expect(screen.getByText("SQL Basics")).toBeInTheDocument();
    expect(screen.getAllByText("Python").length).toBeGreaterThan(0);
  });

  it("requests the catalog with no filter params on first load ('all' -> omitted)", async () => {
    ready([resource()]);
    render(<LearningBrowseView />);
    await screen.findByText("Python for Everybody");
    expect(mocks.listLearningResources).toHaveBeenCalledWith({
      difficulty: undefined,
      resourceType: undefined,
    });
  });

  it("renders the progress summary from the /progress API only", async () => {
    ready(
      [resource()],
      [
        progressRow({ resource_id: "a", status: "SAVED" }),
        progressRow({ resource_id: "b", status: "IN_PROGRESS" }),
        progressRow({ resource_id: "c", status: "COMPLETED" }),
        progressRow({ resource_id: "d", status: "COMPLETED" }),
      ],
    );
    render(<LearningBrowseView />);
    const saved = (await screen.findByText("Saved")).closest("div");
    const inProgress = screen.getByText("In progress").closest("div");
    const completed = screen.getByText("Completed").closest("div");
    expect(within(saved as HTMLElement).getByText("1")).toBeInTheDocument();
    expect(within(inProgress as HTMLElement).getByText("1")).toBeInTheDocument();
    expect(within(completed as HTMLElement).getByText("2")).toBeInTheDocument();
  });

  it("shows the empty state when the API returns nothing", async () => {
    ready([]);
    render(<LearningBrowseView />);
    expect(
      await screen.findByText("No learning resources available right now"),
    ).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.listLearningResources.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    mocks.listMyLearningProgress.mockResolvedValue({ progress: [] });
    render(<LearningBrowseView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("filters the visible list client-side by the title/provider search, without re-requesting", async () => {
    ready([
      resource({ id: "res-1", title: "Python for Everybody", provider: "py4e" }),
      resource({ id: "res-2", title: "SQL Basics", provider: "SQLBolt" }),
    ]);
    render(<LearningBrowseView />);
    await screen.findByText("Python for Everybody");
    const callsBefore = mocks.listLearningResources.mock.calls.length;

    await userEvent.type(screen.getByLabelText("Search learning resources"), "sql basics");

    expect(screen.queryByText("Python for Everybody")).not.toBeInTheDocument();
    expect(screen.getByText("SQL Basics")).toBeInTheDocument();
    // client-side only -- the catalog was not re-fetched
    expect(mocks.listLearningResources.mock.calls.length).toBe(callsBefore);
  });
});

// The Select-driven difficulty/type filters wire straight through
// listLearningResources({ difficulty, resourceType }); the exact query
// string that produces is covered by lib/student/__tests__/learning.test.ts.
describe("learning filter helpers", () => {
  it("EMPTY_LEARNING_FILTERS is inactive; any change is active", () => {
    expect(learningFiltersActive(EMPTY_LEARNING_FILTERS)).toBe(false);
    expect(learningFiltersActive({ ...EMPTY_LEARNING_FILTERS, search: "x" })).toBe(true);
    expect(learningFiltersActive({ ...EMPTY_LEARNING_FILTERS, difficulty: "Advanced" })).toBe(true);
    expect(learningFiltersActive({ ...EMPTY_LEARNING_FILTERS, resourceType: "VIDEO" })).toBe(true);
  });
});
