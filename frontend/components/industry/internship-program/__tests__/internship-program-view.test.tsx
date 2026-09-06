import { afterEach, describe, expect, it, vi } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";

const mocks = vi.hoisted(() => ({
  getInternshipProgram: vi.fn(),
  createInternshipProgram: vi.fn(),
  updateInternshipProgram: vi.fn(),
  publishInternshipProgram: vi.fn(),
  setInternshipProgramSkills: vi.fn(),
  createProgramModule: vi.fn(),
  updateProgramModule: vi.fn(),
  reorderProgramModules: vi.fn(),
  createModuleItem: vi.fn(),
  updateModuleItem: vi.fn(),
  reorderModuleItems: vi.fn(),
  createProgramAssignment: vi.fn(),
  updateProgramAssignment: vi.fn(),
  reorderProgramAssignments: vi.fn(),
}));

vi.mock("@/lib/industry/internship-program", () => mocks);

import { InternshipProgramView } from "@/components/industry/internship-program/internship-program-view";
import { ApiError } from "@/lib/api";
import type { InternshipProgramBundle } from "@/types/internship-program";

function bundle(overrides: Partial<InternshipProgramBundle> = {}): InternshipProgramBundle {
  return {
    internship: { id: "int-1", title: "ML Engineering Intern", status: "PUBLISHED" },
    program: {
      id: "prog-1",
      internship_id: "int-1",
      title: "ML Program",
      summary: "Learn ML.",
      estimated_weeks: 6,
      status: "DRAFT",
      published_at: null,
      created_at: null,
      updated_at: null,
    },
    modules: [
      {
        id: "m1",
        title: "Python Foundations",
        description: "Basics.",
        order_index: 0,
        is_published: true,
        items: [
          {
            id: "i1",
            module_id: "m1",
            title: "Intro video",
            item_type: "VIDEO",
            content_url: "https://x/v",
            content_text: null,
            order_index: 0,
            is_published: true,
          },
        ],
        assignments: [],
      },
    ],
    skills: [{ skill_id: "sk-py", skill_name: "Python", requirement: "REQUIRED" }],
    available_skills: [
      { skill_id: "sk-py", skill_name: "Python", required_level: "Advanced", importance: "CORE" },
      { skill_id: "sk-sql", skill_name: "SQL", required_level: "Intermediate", importance: "IMPORTANT" },
    ],
    ...overrides,
  };
}

describe("InternshipProgramView", () => {
  afterEach(() => vi.resetAllMocks());

  it("shows a loading state then the program", async () => {
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle());
    render(<InternshipProgramView internshipId="int-1" />);
    expect(screen.getByLabelText("Loading program")).toBeInTheDocument();

    expect(await screen.findByRole("heading", { name: "Internship Program" })).toBeInTheDocument();
    expect(screen.getByText("Draft")).toBeInTheDocument();
    expect(screen.getByText("Python Foundations")).toBeInTheDocument();
    expect(screen.getByText("Intro video")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: /publish program/i })).toBeInTheDocument();
  });

  it("shows a 404 message for an internship that isn't yours", async () => {
    mocks.getInternshipProgram.mockRejectedValueOnce(new ApiError(404, "nope"));
    render(<InternshipProgramView internshipId="int-x" />);
    expect(
      await screen.findByText("This internship doesn't exist or isn't yours."),
    ).toBeInTheDocument();
  });

  it("shows the no-program state and creates a program", async () => {
    const user = userEvent.setup();
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle({ program: null, modules: [], skills: [] }));
    mocks.createInternshipProgram.mockResolvedValueOnce(bundle());

    render(<InternshipProgramView internshipId="int-1" />);
    expect(await screen.findByText("No program yet")).toBeInTheDocument();

    await user.type(screen.getByLabelText("Program name"), "ML Program");
    await user.click(screen.getByRole("button", { name: /create program/i }));

    await waitFor(() =>
      expect(mocks.createInternshipProgram).toHaveBeenCalledWith("int-1", { title: "ML Program" }),
    );
    expect(await screen.findByText("Program information")).toBeInTheDocument();
  });

  it("adds a module", async () => {
    const user = userEvent.setup();
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle({ modules: [] }));
    mocks.createProgramModule.mockResolvedValueOnce(bundle());

    render(<InternshipProgramView internshipId="int-1" />);
    await user.click(await screen.findByRole("button", { name: /add module/i }));
    await user.type(screen.getByLabelText("Module title"), "New Module");
    await user.click(screen.getByRole("button", { name: /^add module$/i }));

    await waitFor(() =>
      expect(mocks.createProgramModule).toHaveBeenCalledWith("int-1", { title: "New Module" }),
    );
  });

  it("adds an item to a module (URL required for a LINK)", async () => {
    const user = userEvent.setup();
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle());
    mocks.createModuleItem.mockResolvedValueOnce(bundle());

    render(<InternshipProgramView internshipId="int-1" />);
    await user.click(await screen.findByRole("button", { name: /add item/i }));
    await user.type(screen.getByLabelText("Item title"), "Reading");
    await user.type(screen.getByLabelText("URL"), "https://example.com");
    await user.click(screen.getByRole("button", { name: /^add item$/i }));

    await waitFor(() =>
      expect(mocks.createModuleItem).toHaveBeenCalledWith("int-1", "m1", {
        title: "Reading",
        item_type: "LINK",
        content_url: "https://example.com",
        content_text: null,
      }),
    );
  });

  it("adds an assignment to a module", async () => {
    const user = userEvent.setup();
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle());
    mocks.createProgramAssignment.mockResolvedValueOnce(bundle());

    render(<InternshipProgramView internshipId="int-1" />);
    await user.click(await screen.findByRole("button", { name: /add assignment/i }));
    await user.type(screen.getByLabelText(/assignment title/i), "Build a CLI");
    await user.click(screen.getByRole("button", { name: /^add assignment$/i }));

    await waitFor(() =>
      expect(mocks.createProgramAssignment).toHaveBeenCalledWith(
        "int-1",
        "m1",
        expect.objectContaining({ title: "Build a CLI", assignment_type: "ASSIGNMENT" }),
      ),
    );
  });

  it("hides an assignment from students via the update API (no delete)", async () => {
    const user = userEvent.setup();
    mocks.getInternshipProgram.mockResolvedValueOnce(
      bundle({
        modules: [
          {
            id: "m1",
            title: "Python Foundations",
            description: null,
            order_index: 0,
            is_published: true,
            items: [],
            assignments: [
              {
                id: "as1",
                module_id: "m1",
                program_id: "prog-1",
                title: "Build a CLI",
                description: null,
                instructions: null,
                assignment_type: "ASSIGNMENT",
                is_required: true,
                is_published: true,
                order_index: 0,
                due_offset_days: null,
                submission_kind: "LINK",
                repo_required: false,
                live_url_expected: false,
                max_score: null,
                linked_skill_id: null,
                created_at: null,
                updated_at: null,
              },
            ],
          },
        ],
      }),
    );
    mocks.updateProgramAssignment.mockResolvedValueOnce(bundle());

    render(<InternshipProgramView internshipId="int-1" />);
    await user.click(await screen.findByRole("button", { name: /hide assignment from students/i }));

    await waitFor(() =>
      expect(mocks.updateProgramAssignment).toHaveBeenCalledWith("int-1", "m1", "as1", {
        is_published: false,
      }),
    );
  });

  it("moves a module down via the reorder API", async () => {
    const user = userEvent.setup();
    const two = bundle({
      modules: [
        { id: "m1", title: "A", description: null, order_index: 0, is_published: true, items: [], assignments: [] },
        { id: "m2", title: "B", description: null, order_index: 1, is_published: true, items: [], assignments: [] },
      ],
    });
    mocks.getInternshipProgram.mockResolvedValueOnce(two);
    mocks.reorderProgramModules.mockResolvedValueOnce(two);

    render(<InternshipProgramView internshipId="int-1" />);
    await screen.findByText("A");
    await user.click(screen.getAllByRole("button", { name: "Move module down" })[0]);

    await waitFor(() =>
      expect(mocks.reorderProgramModules).toHaveBeenCalledWith("int-1", ["m2", "m1"]),
    );
  });

  it("saves program skills as a replace-set with the required/optional choice", async () => {
    const user = userEvent.setup();
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle());
    mocks.setInternshipProgramSkills.mockResolvedValueOnce(bundle());

    render(<InternshipProgramView internshipId="int-1" />);
    await screen.findByText("Skills");

    // Python starts REQUIRED; flip it to Optional, then save the replace-set.
    await user.click(screen.getByRole("button", { name: "Optional" }));
    await user.click(screen.getByRole("button", { name: /save skills/i }));

    await waitFor(() =>
      expect(mocks.setInternshipProgramSkills).toHaveBeenCalledWith("int-1", [
        { skill_id: "sk-py", requirement: "OPTIONAL" },
      ]),
    );
  });

  it("cannot select a skill that isn't one of the internship's skills", async () => {
    // available_skills is the ONLY source -- the add dropdown never offers
    // anything outside it, and the backend rejects any other id anyway.
    mocks.getInternshipProgram.mockResolvedValueOnce(
      bundle({ available_skills: [{ skill_id: "sk-py", skill_name: "Python", required_level: null, importance: null }], skills: [] }),
    );
    render(<InternshipProgramView internshipId="int-1" />);
    await screen.findByText("Skills");
    // Only "Python" is offerable; "Rust" (not in available_skills) never appears.
    expect(screen.queryByText("Rust")).not.toBeInTheDocument();
  });

  it("publishes the program after confirmation", async () => {
    const user = userEvent.setup();
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle());
    mocks.publishInternshipProgram.mockResolvedValueOnce(bundle({ program: { ...bundle().program!, status: "PUBLISHED" } }));

    render(<InternshipProgramView internshipId="int-1" />);
    await user.click(await screen.findByRole("button", { name: /publish program/i }));
    await user.click(await screen.findByRole("button", { name: /^publish$/i }));

    await waitFor(() => expect(mocks.publishInternshipProgram).toHaveBeenCalledWith("int-1"));
    expect(await screen.findByText(/published — visible to interns/i)).toBeInTheDocument();
  });

  it("surfaces a mutation error at the top of the page", async () => {
    const user = userEvent.setup();
    mocks.getInternshipProgram.mockResolvedValueOnce(bundle());
    mocks.updateInternshipProgram.mockRejectedValueOnce(new ApiError(422, "title too long"));

    render(<InternshipProgramView internshipId="int-1" />);
    await screen.findByText("Program information");
    await user.clear(screen.getByLabelText("Program name"));
    await user.type(screen.getByLabelText("Program name"), "Renamed");
    await user.click(screen.getByRole("button", { name: "Save" }));

    expect(await screen.findByText("title too long")).toBeInTheDocument();
  });
});
