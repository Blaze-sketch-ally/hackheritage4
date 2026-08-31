import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const { listMyProjects, createProject, updateProject, deleteProject } = vi.hoisted(() => ({
  listMyProjects: vi.fn(),
  createProject: vi.fn(),
  updateProject: vi.fn(),
  deleteProject: vi.fn(),
}));

vi.mock("@/lib/student/portfolio", () => ({
  listMyProjects,
  createProject,
  updateProject,
  deleteProject,
  // Certification functions are unused by ProjectList but imported by
  // the same module in other components -- not needed here.
}));

import { ProjectList } from "@/components/portfolio/project-list";
import { ApiError } from "@/lib/api";

function project(overrides = {}) {
  return {
    id: "p1",
    student_id: "s1",
    title: "Campus Event Finder",
    description: "A React + FastAPI app for discovering campus events.",
    technologies: ["React", "FastAPI"],
    project_url: "https://events.example.com",
    github_url: "https://github.com/example/events",
    created_at: "2026-01-01T00:00:00Z",
    updated_at: "2026-01-01T00:00:00Z",
    ...overrides,
  };
}

describe("ProjectList", () => {
  afterEach(() => vi.clearAllMocks());

  it("shows a loading state before data arrives", () => {
    listMyProjects.mockReturnValue(new Promise(() => {}));
    render(<ProjectList />);
    expect(screen.getByLabelText("Loading projects")).toBeInTheDocument();
  });

  it("shows the empty state with no mock data when there are no projects", async () => {
    listMyProjects.mockResolvedValue({ projects: [] });
    render(<ProjectList />);
    expect(await screen.findByText("Add your first project to showcase your work.")).toBeInTheDocument();
  });

  it("renders a project once loaded", async () => {
    listMyProjects.mockResolvedValue({ projects: [project()] });
    render(<ProjectList />);
    expect(await screen.findByText("Campus Event Finder")).toBeInTheDocument();
    expect(screen.getByText("React")).toBeInTheDocument();
    expect(screen.getByText("GitHub")).toBeInTheDocument();
  });

  it("shows an error state with retry when the API call fails", async () => {
    listMyProjects.mockRejectedValue(new ApiError(500, "Backend unavailable right now."));
    render(<ProjectList />);
    expect(await screen.findByText("Backend unavailable right now.")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /try again/i })).toBeInTheDocument();
  });

  it("retry re-fetches the list", async () => {
    listMyProjects
      .mockRejectedValueOnce(new ApiError(500, "Backend unavailable right now."))
      .mockResolvedValueOnce({ projects: [project()] });
    render(<ProjectList />);
    await screen.findByText("Backend unavailable right now.");

    await userEvent.click(screen.getByRole("button", { name: /try again/i }));

    await waitFor(() => expect(listMyProjects).toHaveBeenCalledTimes(2));
    expect(await screen.findByText("Campus Event Finder")).toBeInTheDocument();
  });

  it("creates a project through the inline form", async () => {
    listMyProjects.mockResolvedValueOnce({ projects: [] }).mockResolvedValueOnce({ projects: [project()] });
    createProject.mockResolvedValue(project());
    render(<ProjectList />);
    await screen.findByText("Add your first project to showcase your work.");

    await userEvent.click(screen.getByRole("button", { name: /add project/i }));
    await userEvent.type(screen.getByLabelText("Project title"), "Campus Event Finder");
    await userEvent.type(screen.getByLabelText("Description"), "A React + FastAPI app for discovering campus events.");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(createProject).toHaveBeenCalledTimes(1));
    expect(await screen.findByText("Campus Event Finder")).toBeInTheDocument();
  });

  it("edits an existing project", async () => {
    listMyProjects.mockResolvedValue({ projects: [project()] });
    updateProject.mockResolvedValue(project({ title: "Updated Title" }));
    render(<ProjectList />);
    await screen.findByText("Campus Event Finder");

    await userEvent.click(screen.getByRole("button", { name: /edit project/i }));
    const titleInput = screen.getByLabelText("Project title");
    await userEvent.clear(titleInput);
    await userEvent.type(titleInput, "Updated Title");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    await waitFor(() => expect(updateProject).toHaveBeenCalledWith("p1", expect.objectContaining({ title: "Updated Title" })));
  });

  it("deletes a project after confirmation", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(true);
    listMyProjects.mockResolvedValueOnce({ projects: [project()] }).mockResolvedValueOnce({ projects: [] });
    deleteProject.mockResolvedValue(undefined);
    render(<ProjectList />);
    await screen.findByText("Campus Event Finder");

    await userEvent.click(screen.getByRole("button", { name: /delete project/i }));

    await waitFor(() => expect(deleteProject).toHaveBeenCalledWith("p1"));
    confirmSpy.mockRestore();
  });

  it("does not delete when the confirmation is declined", async () => {
    const confirmSpy = vi.spyOn(window, "confirm").mockReturnValue(false);
    listMyProjects.mockResolvedValue({ projects: [project()] });
    render(<ProjectList />);
    await screen.findByText("Campus Event Finder");

    await userEvent.click(screen.getByRole("button", { name: /delete project/i }));

    expect(deleteProject).not.toHaveBeenCalled();
    confirmSpy.mockRestore();
  });

  it("shows a validation error message when create fails", async () => {
    listMyProjects.mockResolvedValue({ projects: [] });
    createProject.mockRejectedValue(new ApiError(422, "Must be a valid http(s) URL."));
    render(<ProjectList />);
    await screen.findByText("Add your first project to showcase your work.");

    await userEvent.click(screen.getByRole("button", { name: /add project/i }));
    await userEvent.type(screen.getByLabelText("Project title"), "X");
    await userEvent.type(screen.getByLabelText("Description"), "Y");
    await userEvent.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("Must be a valid http(s) URL.")).toBeInTheDocument();
  });
});
