import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor, within } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  listProjects: vi.fn(),
  createProject: vi.fn(),
  updateProject: vi.fn(),
  deleteProject: vi.fn(),
  fetchActiveSkills: vi.fn(),
}));

vi.mock("@/lib/student/portfolio", () => ({
  listProjects: mocks.listProjects,
  createProject: mocks.createProject,
  updateProject: mocks.updateProject,
  deleteProject: mocks.deleteProject,
}));
vi.mock("@/lib/student/skills", () => ({ fetchActiveSkills: mocks.fetchActiveSkills }));
vi.mock("@/lib/supabase/client", () => ({ createClient: () => ({}) }));

import { ProjectsView } from "@/components/student/portfolio/projects-view";
import { ApiError } from "@/lib/api";
import type { StudentProject } from "@/types/student-portfolio";

function project(overrides: Partial<StudentProject> = {}): StudentProject {
  return {
    id: "p1",
    title: "Skill Portal",
    description: "A portfolio app.",
    project_url: "https://example.com",
    repo_url: null,
    start_date: "2026-01-01",
    end_date: "2026-03-01",
    is_ongoing: false,
    skills: [{ skill_id: "s1", skill_name: "Python", category_name: "Programming" }],
    created_at: "2026-09-01T00:00:00Z",
    updated_at: "2026-09-01T00:00:00Z",
    ...overrides,
  };
}

describe("ProjectsView", () => {
  afterEach(() => vi.resetAllMocks());

  it("renders a truthful empty state (no fabricated projects)", async () => {
    mocks.listProjects.mockResolvedValue({ projects: [] });
    render(<ProjectsView />);
    expect(await screen.findByText("No projects yet")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /add your first project/i })).toBeInTheDocument();
  });

  it("renders the student's real projects from the API", async () => {
    mocks.listProjects.mockResolvedValue({ projects: [project(), project({ id: "p2", title: "Second" })] });
    render(<ProjectsView />);
    expect(await screen.findByText("Skill Portal")).toBeInTheDocument();
    expect(screen.getByText("Second")).toBeInTheDocument();
    expect(screen.getAllByText("Python").length).toBeGreaterThan(0);
  });

  it("shows an error state with retry", async () => {
    mocks.listProjects.mockRejectedValueOnce(new ApiError(500, "boom")).mockResolvedValueOnce({ projects: [project()] });
    render(<ProjectsView />);
    await userEvent.click(await screen.findByRole("button", { name: /try again/i }));
    expect(await screen.findByText("Skill Portal")).toBeInTheDocument();
  });

  it("creates a project through the dialog and never sends an ownership field", async () => {
    mocks.listProjects.mockResolvedValue({ projects: [] });
    mocks.fetchActiveSkills.mockResolvedValue([]);
    mocks.createProject.mockResolvedValue(project({ id: "new", title: "New App" }));
    render(<ProjectsView />);

    await userEvent.click(await screen.findByRole("button", { name: /add your first project/i }));
    await userEvent.type(screen.getByLabelText("Title *"), "New App");
    await userEvent.click(screen.getByRole("button", { name: /add project/i }));

    await waitFor(() => expect(mocks.createProject).toHaveBeenCalledTimes(1));
    const body = mocks.createProject.mock.calls[0][0];
    expect(body.title).toBe("New App");
    for (const f of ["student_id", "owner_id", "id", "is_verified"]) {
      expect(body).not.toHaveProperty(f);
    }
    expect(await screen.findByText("New App")).toBeInTheDocument();
  });

  it("blocks submit when the title is empty", async () => {
    mocks.listProjects.mockResolvedValue({ projects: [] });
    mocks.fetchActiveSkills.mockResolvedValue([]);
    render(<ProjectsView />);
    await userEvent.click(await screen.findByRole("button", { name: /add your first project/i }));
    await userEvent.click(screen.getByRole("button", { name: /add project/i }));
    expect(await screen.findByText(/give your project a title/i)).toBeInTheDocument();
    expect(mocks.createProject).not.toHaveBeenCalled();
  });

  it("deletes a project only after confirmation", async () => {
    mocks.listProjects.mockResolvedValue({ projects: [project()] });
    mocks.deleteProject.mockResolvedValue(undefined);
    render(<ProjectsView />);

    await userEvent.click(await screen.findByRole("button", { name: /delete/i }));
    // confirmation dialog
    const dialog = await screen.findByRole("dialog");
    expect(within(dialog).getByText(/this can't be undone/i)).toBeInTheDocument();
    expect(mocks.deleteProject).not.toHaveBeenCalled();
    await userEvent.click(within(dialog).getByRole("button", { name: /delete project/i }));
    await waitFor(() => expect(mocks.deleteProject).toHaveBeenCalledWith("p1"));
    await waitFor(() => expect(screen.queryByText("Skill Portal")).not.toBeInTheDocument());
  });

  it("surfaces a backend 422 for unknown skill ids without crashing", async () => {
    mocks.listProjects.mockResolvedValue({ projects: [] });
    mocks.fetchActiveSkills.mockResolvedValue([]);
    mocks.createProject.mockRejectedValue(new ApiError(422, "Unknown skill id(s): deadbeef"));
    render(<ProjectsView />);
    await userEvent.click(await screen.findByRole("button", { name: /add your first project/i }));
    await userEvent.type(screen.getByLabelText("Title *"), "P");
    await userEvent.click(screen.getByRole("button", { name: /add project/i }));
    expect(await screen.findByText(/Unknown skill id/i)).toBeInTheDocument();
  });
});
