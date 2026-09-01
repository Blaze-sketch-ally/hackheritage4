import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getProjects: vi.fn(),
  publishProject: vi.fn(),
  closeProject: vi.fn(),
  archiveProject: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/projects", () => ({
  getProjects: mocks.getProjects,
  publishProject: mocks.publishProject,
  closeProject: mocks.closeProject,
  archiveProject: mocks.archiveProject,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { ProjectsListView } from "@/components/industry/projects/projects-list-view";
import { ApiError } from "@/lib/api";
import type { IndustryProject } from "@/types/industry-project";

function project(overrides: Partial<IndustryProject> = {}): IndustryProject {
  return {
    id: "project-1",
    industry_id: "industry-1",
    title: "Campus Recommendation Engine",
    description: "Build a recommender.",
    location: "Remote",
    work_mode: "REMOTE",
    duration_months: 3,
    team_size: 4,
    eligibility_criteria: null,
    application_deadline: "2026-12-01",
    start_date: "2026-09-15",
    status: "DRAFT",
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

describe("ProjectsListView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getProjects.mockReturnValue(new Promise(() => {}));
    render(<ProjectsListView />);
    expect(screen.getByText(/Loading your projects/i)).toBeInTheDocument();
  });

  it("shows an error state with retry", async () => {
    mocks.getProjects.mockRejectedValueOnce(new ApiError(500, "Server is down."));
    render(<ProjectsListView />);
    expect(await screen.findByText("Server is down.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("shows the empty state when there are no projects", async () => {
    mocks.getProjects.mockResolvedValueOnce({ projects: [] });
    render(<ProjectsListView />);
    expect(await screen.findByText("No projects yet")).toBeInTheDocument();
  });

  it("lists projects with title and status", async () => {
    mocks.getProjects.mockResolvedValueOnce({
      projects: [project(), project({ id: "project-2", title: "Fraud Detection Model", status: "PUBLISHED" })],
    });
    render(<ProjectsListView />);

    expect(await screen.findByText("Campus Recommendation Engine")).toBeInTheDocument();
    expect(screen.getByText("Fraud Detection Model")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("filters by search text", async () => {
    mocks.getProjects.mockResolvedValueOnce({
      projects: [project(), project({ id: "project-2", title: "Fraud Detection Model" })],
    });
    render(<ProjectsListView />);
    await screen.findByText("Campus Recommendation Engine");

    await userEvent.type(screen.getByLabelText("Search projects"), "fraud");

    expect(screen.queryByText("Campus Recommendation Engine")).not.toBeInTheDocument();
    expect(screen.getByText("Fraud Detection Model")).toBeInTheDocument();
  });

  it("publishes a project through the confirmation dialog", async () => {
    mocks.getProjects.mockResolvedValueOnce({ projects: [project()] });
    mocks.publishProject.mockResolvedValueOnce(project({ status: "PUBLISHED" }));

    render(<ProjectsListView />);
    await screen.findByText("Campus Recommendation Engine");

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishProject).toHaveBeenCalledWith("project-1"));
    expect(await screen.findByText("Project published.")).toBeInTheDocument();
  });

  it("surfaces a publish error from the API", async () => {
    mocks.getProjects.mockResolvedValueOnce({ projects: [project()] });
    mocks.publishProject.mockRejectedValueOnce(
      new ApiError(422, "This project isn't ready to publish. Add: work_mode."),
    );

    render(<ProjectsListView />);
    await screen.findByText("Campus Recommendation Engine");
    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    expect(await screen.findByText(/isn't ready to publish/i)).toBeInTheDocument();
  });
});
