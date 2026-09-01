import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getProject: vi.fn(),
  updateProject: vi.fn(),
  publishProject: vi.fn(),
  closeProject: vi.fn(),
  archiveProject: vi.fn(),
  push: vi.fn(),
}));

vi.mock("@/lib/industry/projects", () => ({
  getProject: mocks.getProject,
  updateProject: mocks.updateProject,
  publishProject: mocks.publishProject,
  closeProject: mocks.closeProject,
  archiveProject: mocks.archiveProject,
}));
vi.mock("next/navigation", () => ({ useRouter: () => ({ push: mocks.push }) }));

import { ProjectDetailView } from "@/components/industry/projects/project-detail-view";
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

describe("ProjectDetailView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state", () => {
    mocks.getProject.mockReturnValue(new Promise(() => {}));
    render(<ProjectDetailView projectId="project-1" />);
    expect(screen.getByText("Loading…")).toBeInTheDocument();
  });

  it("shows a not-found message on a 404", async () => {
    mocks.getProject.mockRejectedValueOnce(new ApiError(404, "Project not found."));
    render(<ProjectDetailView projectId="project-x" />);
    expect(await screen.findByText(/doesn't exist or isn't yours/i)).toBeInTheDocument();
  });

  it("renders project detail with status", async () => {
    mocks.getProject.mockResolvedValueOnce(project());
    render(<ProjectDetailView projectId="project-1" />);

    expect(
      await screen.findByRole("heading", { name: "Campus Recommendation Engine" }),
    ).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getAllByText("Remote").length).toBeGreaterThan(0);
  });

  it("switches to the edit form and saves changes", async () => {
    mocks.getProject.mockResolvedValueOnce(project());
    mocks.updateProject.mockResolvedValueOnce(project({ title: "Updated Recommender" }));

    render(<ProjectDetailView projectId="project-1" />);
    await screen.findByRole("heading", { name: "Campus Recommendation Engine" });

    await userEvent.click(screen.getByRole("button", { name: "Edit" }));
    const title = await screen.findByLabelText("Title");
    await userEvent.clear(title);
    await userEvent.type(title, "Updated Recommender");
    await userEvent.click(screen.getByRole("button", { name: "Save Changes" }));

    await waitFor(() => expect(mocks.updateProject).toHaveBeenCalledTimes(1));
    expect(mocks.updateProject.mock.calls[0][0]).toBe("project-1");
    expect(await screen.findByText("Changes saved.")).toBeInTheDocument();
    expect(screen.getByRole("heading", { name: "Updated Recommender" })).toBeInTheDocument();
  });

  it("publishes via the confirmation dialog", async () => {
    mocks.getProject.mockResolvedValueOnce(project());
    mocks.publishProject.mockResolvedValueOnce(project({ status: "PUBLISHED" }));

    render(<ProjectDetailView projectId="project-1" />);
    await screen.findByRole("heading", { name: "Campus Recommendation Engine" });

    await userEvent.click(screen.getByRole("button", { name: "Publish" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Publish" }));

    await waitFor(() => expect(mocks.publishProject).toHaveBeenCalledWith("project-1"));
    expect(await screen.findByText("Project published.")).toBeInTheDocument();
    expect(screen.getByText("Published")).toBeInTheDocument();
  });

  it("archives a published project via the confirmation dialog", async () => {
    mocks.getProject.mockResolvedValueOnce(project({ status: "PUBLISHED" }));
    mocks.archiveProject.mockResolvedValueOnce(project({ status: "ARCHIVED" }));

    render(<ProjectDetailView projectId="project-1" />);
    await screen.findByRole("heading", { name: "Campus Recommendation Engine" });

    await userEvent.click(screen.getByRole("button", { name: "Archive" }));
    const dialog = await screen.findByRole("dialog");
    await userEvent.click(within(dialog).getByRole("button", { name: "Archive" }));

    await waitFor(() => expect(mocks.archiveProject).toHaveBeenCalledWith("project-1"));
    expect(await screen.findByText("Project archived.")).toBeInTheDocument();
  });

  it("starts in edit mode when initialEdit is set", async () => {
    mocks.getProject.mockResolvedValueOnce(project());
    render(<ProjectDetailView projectId="project-1" initialEdit />);

    expect(await screen.findByRole("heading", { name: "Edit Project" })).toBeInTheDocument();
    expect(screen.getByLabelText("Title")).toHaveValue("Campus Recommendation Engine");
  });
});
